from __future__ import annotations

from dataclasses import dataclass


DEFAULT_CARRIER_WAVELENGTH_M = 0.0107


@dataclass(frozen=True)
class SoCProxyEstimate:
    """Pre-plug-in SoC estimate derived from RSU sensing features."""

    estimated_soc: float
    confidence: float
    features: dict[str, float]


def isac_proxy_features(
    *,
    true_soc: float | None,
    speed_kmh: float,
    distance_to_rsu_km: float,
    rsu_range_km: float,
    decel_mps2: float = 0.0,
    carrier_wavelength_m: float = DEFAULT_CARRIER_WAVELENGTH_M,
) -> dict[str, float]:
    """Build deterministic ISAC-like features for the corridor model."""
    distance_km = max(0.001, float(distance_to_rsu_km))
    speed_mps = max(0.0, float(speed_kmh)) / 3.6
    doppler_hz = 2.0 * speed_mps / max(carrier_wavelength_m, 1e-9)
    range_ratio = min(1.0, distance_km / max(float(rsu_range_km), 0.001))
    soc_component = 0.0 if true_soc is None else (float(true_soc) - 50.0) * 0.015
    rssi_dbm = -42.0 - 20.0 * range_ratio + soc_component
    return {
        "rssi_dbm": round(rssi_dbm, 4),
        "doppler_hz": round(doppler_hz, 4),
        "range_km": round(distance_km, 4),
        "decel_mps2": round(float(decel_mps2), 4),
    }


def estimate_soc_proxy(
    *,
    rssi_dbm: float,
    doppler_hz: float,
    range_km: float,
    decel_mps2: float = 0.0,
    onboard_soc_hint: float | None = None,
) -> SoCProxyEstimate:
    """Estimate pre-arrival SoC from ISAC-style features.

    This deterministic calibrated baseline behaves like a tiny ridge model
    without adding dependencies. If an EV broadcast includes a direct battery
    hint, the proxy fuses it with the sensing-only estimate instead of blindly
    copying it.
    """
    rssi_score = (float(rssi_dbm) + 62.0) * 1.55
    doppler_score = (float(doppler_hz) - 3500.0) / 500.0
    range_penalty = max(0.0, float(range_km)) * 1.8
    decel_penalty = max(0.0, float(decel_mps2)) * 2.2
    sensing_only = 48.0 + rssi_score + doppler_score - range_penalty - decel_penalty
    if onboard_soc_hint is not None:
        estimate = 0.72 * float(onboard_soc_hint) + 0.28 * sensing_only
        confidence = 0.88
    else:
        estimate = sensing_only
        confidence = 0.62
    estimate = max(0.0, min(100.0, estimate))
    return SoCProxyEstimate(
        estimated_soc=round(estimate, 2),
        confidence=round(confidence, 3),
        features={
            "rssi_dbm": round(float(rssi_dbm), 4),
            "doppler_hz": round(float(doppler_hz), 4),
            "range_km": round(float(range_km), 4),
            "decel_mps2": round(float(decel_mps2), 4),
        },
    )
