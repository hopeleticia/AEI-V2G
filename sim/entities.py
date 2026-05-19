from __future__ import annotations

from dataclasses import dataclass, field


NOMINAL_BATTERY_KWH = 72.0
MIN_V2G_SOC_PCT = 20.0


@dataclass
class EV:
    id: str
    km: float
    speed_kmh: float
    battery_pct: float
    destination_km: float
    charge_request: bool
    required_kwh: float
    assigned_station: str | None = None
    connected_until_min: int = 0
    v2g_eligible: bool = False
    v2g_invited: bool = False
    v2g_accepted: bool = False
    # Per-EV battery state fields (Obj-4, P2)
    SoH_k: float = 1.0        # State of Health — capacity fade factor (0–1)
    SoC_req_k: float = 80.0   # Driver's requested SoC at departure (%)
    T_dep_k: float = 60.0     # Declared departure time (minutes from admission)
    soc_trajectory: list = field(default_factory=list)  # [(tick, soc_pct), ...]

    def __post_init__(self) -> None:
        self.battery_pct = max(0.0, min(100.0, self.battery_pct))
        self.SoH_k = max(0.1, min(1.0, self.SoH_k))
        self.SoC_req_k = max(0.0, min(100.0, self.SoC_req_k))
        if not self.soc_trajectory:
            self.record_soc(0)

    @property
    def usable_battery_kwh(self) -> float:
        return max(0.1, self.SoH_k * NOMINAL_BATTERY_KWH)

    def kwh_to_requested_soc(self) -> float:
        soc_gap_pct = max(0.0, self.SoC_req_k - self.battery_pct)
        return soc_gap_pct / 100.0 * self.usable_battery_kwh

    def refresh_required_kwh_for_request(self) -> None:
        self.required_kwh = max(self.required_kwh, self.kwh_to_requested_soc())

    def has_met_requested_soc(self, tolerance_pct: float = 0.01) -> bool:
        return self.battery_pct + tolerance_pct >= self.SoC_req_k

    def record_soc(self, tick: int | float) -> None:
        self.soc_trajectory.append((tick, round(self.battery_pct, 2)))

    def add_charge_kwh(self, kwh: float, tick: int | float) -> float:
        accepted_kwh = max(0.0, min(kwh, (100.0 - self.battery_pct) / 100.0 * self.usable_battery_kwh))
        self.battery_pct = min(100.0, self.battery_pct + accepted_kwh / self.usable_battery_kwh * 100.0)
        self.record_soc(tick)
        return accepted_kwh

    def discharge_v2g_kwh(self, requested_kwh: float, tick: int | float) -> float:
        max_discharge_kwh = max(0.0, (self.battery_pct - MIN_V2G_SOC_PCT) / 100.0 * self.usable_battery_kwh)
        supplied_kwh = max(0.0, min(requested_kwh, max_discharge_kwh))
        self.battery_pct = max(MIN_V2G_SOC_PCT, self.battery_pct - supplied_kwh / self.usable_battery_kwh * 100.0)
        if supplied_kwh > 0:
            self.record_soc(tick)
        return supplied_kwh

    def advance(self, minutes: float) -> None:
        self.km = min(self.destination_km, self.km + self.speed_kmh * minutes / 60.0)
        self.battery_pct = max(0.0, self.battery_pct - 0.16 * minutes)


@dataclass
class Station:
    id: str
    km: float
    max_kw: float
    slots: int
    base_price: float
    active_evs: list[EV] = field(default_factory=list)
    queue: list[EV] = field(default_factory=list)
    reservations: dict[str, dict] = field(default_factory=dict)
    energy_delivered_kwh: float = 0.0
    v2g_supplied_kwh: float = 0.0

    @property
    def current_load_kw(self) -> float:
        return min(self.max_kw, len(self.active_evs) * 55.0)

    @property
    def available_slots(self) -> int:
        return max(0, self.slots - len(self.active_evs) - len(self.reservations))

    @property
    def queue_depth(self) -> int:
        return len(self.queue)

    @property
    def utilization(self) -> float:
        return min(1.0, self.current_load_kw / self.max_kw)

    def estimated_wait_minutes(self) -> float:
        if self.available_slots:
            return 0.0
        return 10.0 + 8.0 * self.queue_depth

    def reserve_slot(self, ev_id: str, eta_min: float, tick: int | float, ttl_min: float = 30.0) -> dict:
        reservation = {
            "ev_id": ev_id,
            "station_id": self.id,
            "eta_min": round(max(0.0, float(eta_min)), 3),
            "created_tick": tick,
            "expires_tick": float(tick) + max(1.0, float(ttl_min)),
            "status": "reserved",
        }
        self.reservations[ev_id] = reservation
        return reservation

    def release_reservation(self, ev_id: str) -> dict | None:
        return self.reservations.pop(ev_id, None)

    def expire_reservations(self, tick: int | float) -> list[dict]:
        expired: list[dict] = []
        for ev_id, reservation in list(self.reservations.items()):
            if float(tick) >= float(reservation["expires_tick"]):
                reservation["status"] = "expired"
                expired.append(reservation)
                del self.reservations[ev_id]
        return expired
