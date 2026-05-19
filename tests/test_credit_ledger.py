from integration.v2g_dispatcher import apply_v2g
from logging_layer.chain_client import _KWH_PER_CREDIT
from sim.entities import EV, Station


def test_v2g_result_contains_credit_settlement():
    station = Station("s1", 1.0, 300.0, 2, 0.3)
    station.active_evs.append(EV("ev_credit", 1.0, 0.0, 80.0, 10.0, False, 0.0))

    result = apply_v2g({"s1": station}, dispatch_kw=12.0, tick_minutes=60.0, buy_price=0.5)

    assert result["credits_awarded"] == int(result["supplied_kwh"] / _KWH_PER_CREDIT)
    assert result["credit_ledger_mode"] in {"local_hash_only", "on_chain"}
    assert result["settlements"][0]["ev_id"] == "ev_credit"
    assert result["settlements"][0]["credits_awarded"] == result["credits_awarded"]
    assert "credit_ledger_status" in result["settlements"][0]


def test_v2g_settlement_uses_credit_client_when_provided():
    class FakeCreditClient:
        def award_credits(self, ev_id, kwh, station_id):
            return {
                "ev_id": ev_id,
                "station_id": station_id,
                "kwh": kwh,
                "credits_awarded": int(kwh / _KWH_PER_CREDIT),
                "tx_hash": "0xabc123",
                "ledger_mode": "on_chain",
                "ledger_status": "submitted",
            }

    station = Station("s1", 1.0, 300.0, 2, 0.3)
    station.active_evs.append(EV("ev_credit", 1.0, 0.0, 80.0, 10.0, False, 0.0))

    result = apply_v2g(
        {"s1": station},
        dispatch_kw=12.0,
        tick_minutes=60.0,
        buy_price=0.5,
        credit_client=FakeCreditClient(),
    )

    assert result["credit_ledger_mode"] == "on_chain"
    assert result["credit_ledger_transactions"] == 1
    assert result["credit_ledger_failures"] == 0
    assert result["settlements"][0]["credit_ledger_tx_hash"] == "0xabc123"


def test_credit_ledger_contract_declares_required_functions():
    source = open("contracts/CreditLedger.sol", encoding="utf-8").read()

    assert "function award_credits" in source
    assert "function redeem_credits" in source
    assert "function get_balance" in source
    assert "function get_transaction_history" in source
