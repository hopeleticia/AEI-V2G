from __future__ import annotations

from typing import Any


CREDIT_KWH_PER_POINT = 0.5
_CREDIT_CLIENT: Any = None
_CREDIT_CLIENT_READY = False


def _credit_client():
    """Return optional on-chain credit client; None keeps settlement local."""
    global _CREDIT_CLIENT, _CREDIT_CLIENT_READY
    if _CREDIT_CLIENT_READY:
        return _CREDIT_CLIENT
    _CREDIT_CLIENT_READY = True
    try:
        from logging_layer.chain_client import build_from_env
        _CREDIT_CLIENT = build_from_env()
    except Exception:
        _CREDIT_CLIENT = None
    return _CREDIT_CLIENT


def apply_v2g(
    stations: dict,
    dispatch_kw: float,
    tick_minutes: float,
    buy_price: float,
    tick: int | float = 0,
    credit_client: Any = None,
) -> dict:
    remaining_kw = dispatch_kw
    accepted = 0
    invited = 0
    supplied_kwh = 0.0
    revenue = 0.0
    credits_awarded = 0
    credit_ledger_transactions = 0
    credit_ledger_failures = 0
    credit_ledger_statuses: dict[str, int] = {}
    settlements: list[dict] = []
    ledger = credit_client
    for station in stations.values():
        if remaining_kw <= 0:
            break
        for ev in station.active_evs:
            if ev.battery_pct < 55:
                continue
            invited += 1
            ev.v2g_invited = True
            if ev.battery_pct >= 62:
                ev.v2g_accepted = True
                accepted += 1
                kw = min(12.0, remaining_kw)
                requested_kwh = kw * tick_minutes / 60.0
                kwh = ev.discharge_v2g_kwh(requested_kwh, tick)
                if kwh <= 0:
                    continue
                ev.refresh_required_kwh_for_request()
                station.v2g_supplied_kwh += kwh
                supplied_kwh += kwh
                ev_revenue = kwh * buy_price
                revenue += ev_revenue
                ev_credits = int(kwh / CREDIT_KWH_PER_POINT)
                credits_awarded += ev_credits
                settlement = {
                    "ev_id": ev.id,
                    "station_id": station.id,
                    "kwh_supplied": round(kwh, 6),
                    "revenue": round(ev_revenue, 6),
                    "credits_awarded": ev_credits,
                    "credit_ledger_mode": "local_hash_only",
                    "credit_ledger_status": "local_only",
                    "credit_ledger_tx_hash": None,
                    "credit_ledger_block_number": None,
                }
                if ledger is not None and credit_client is not None:
                    ledger_result = ledger.award_credits(ev.id, kwh, station.id)
                    settlement["credit_ledger_mode"] = ledger_result.get("ledger_mode", "on_chain")
                    settlement["credit_ledger_status"] = ledger_result.get("ledger_status", "failed")
                    settlement["credit_ledger_tx_hash"] = ledger_result.get("tx_hash")
                    settlement["credit_ledger_block_number"] = ledger_result.get("block_number")
                    credit_ledger_statuses[settlement["credit_ledger_status"]] = (
                        credit_ledger_statuses.get(settlement["credit_ledger_status"], 0) + 1
                    )
                    if settlement["credit_ledger_tx_hash"] and settlement["credit_ledger_status"] in {"success", "submitted"}:
                        credit_ledger_transactions += 1
                    elif ev_credits > 0 and settlement["credit_ledger_mode"] == "on_chain":
                        credit_ledger_failures += 1
                settlements.append(settlement)
                remaining_kw -= kwh * 60.0 / max(tick_minutes, 1e-9)
    if credit_client is None:
        credits_awarded = int(supplied_kwh / CREDIT_KWH_PER_POINT)
    return {
        "invited": invited,
        "accepted": accepted,
        "supplied_kwh": supplied_kwh,
        "revenue": revenue,
        "credits_awarded": credits_awarded,
        "credit_ledger_transactions": credit_ledger_transactions,
        "credit_ledger_failures": credit_ledger_failures,
        "credit_ledger_mode": "on_chain" if ledger is not None and credit_client is not None else "local_hash_only",
        "credit_ledger_statuses": credit_ledger_statuses,
        "settlements": settlements,
    }
