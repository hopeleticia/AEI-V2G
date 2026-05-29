from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

def _load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE entries without overriding the shell environment."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

_RPC_URL     = os.environ.get("AEI_ETH_RPC_URL") or os.environ.get("RPC_URL", "https://purechainnode.com:8547")
_ACCOUNT     = os.environ.get("AEI_ETH_ACCOUNT",     "")
_PRIVATE_KEY = os.environ.get("AEI_ETH_PRIVATE_KEY") or os.environ.get("PRIVATE_KEY", "")
_CREDIT_LEDGER_ADDRESS = os.environ.get("AEI_CREDIT_LEDGER_ADDRESS", "")
def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


_GAS_PRICE_WEI = _env_int("AEI_ETH_GAS_PRICE_WEI", 0)
_TX_TIMEOUT_SECONDS = _env_int("AEI_ETH_TX_TIMEOUT_SECONDS", 120)

# Account #3 is kept as the immutable log sink — not assigned to any Pi node.
# All nodes send 0-ETH transactions to this address with decision hashes
# as calldata, creating a tamper-evident on-chain audit trail.
_LOG_SINK = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
_KWH_PER_CREDIT = 0.5

_CREDIT_LEDGER_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "evId", "type": "string"},
            {"internalType": "string", "name": "stationId", "type": "string"},
            {"internalType": "uint256", "name": "kwhMilli", "type": "uint256"},
        ],
        "name": "award_credits",
        "outputs": [{"internalType": "uint256", "name": "creditsAwarded", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "evId", "type": "string"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "redeem_credits",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "evId", "type": "string"}],
        "name": "get_balance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Node → Ethereum account mapping (publicly known Hardhat test accounts):
#   pi1 lava-validator    → Account #0  0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
#   pi2 station-validator → Account #1  0x70997970C51812dc3A010C7d01b50e0d17dc79C8
#   pi3 station-validator → Account #2  0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
#   pi5 rsu-observer      → Account #4  0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65
#   pi6 grid-observer     → Account #5  0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc
#   sink / aggregator     → Account #3  0x90F79bf6EB2c4f870365E785982E1f101E93b906
# WARNING: These are publicly known test-network credentials — never use on mainnet.

try:
    from web3 import Web3          # type: ignore[import]
    _WEB3_AVAILABLE = True
except ImportError:
    _WEB3_AVAILABLE = False


def _normalize_tx_hash(value) -> Optional[str]:
    if value is None:
        return None
    tx_hash = value.hex() if hasattr(value, "hex") else str(value)
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    return tx_hash


class ChainClient:
    """
    Anchors AEI-V2G decision hashes on the private Ethereum chain.

    Each call to ``anchor()`` sends a 0-ETH transaction to ``_LOG_SINK``
    with the payload ``event_type:sha256_hash`` encoded as hex calldata.
    This makes every LAVA routing and V2G dispatch decision externally
    verifiable and immutable.

    Thread-safe: nonce management is protected by an internal lock.
    """

    def __init__(
        self,
        rpc_url:     str = _RPC_URL,
        account:     str = _ACCOUNT,
        private_key: str = _PRIVATE_KEY,
        credit_ledger_address: str = _CREDIT_LEDGER_ADDRESS,
    ) -> None:
        if not _WEB3_AVAILABLE:
            raise RuntimeError("web3 is required — run: pip install web3")
        if not private_key:
            raise ValueError(
                "AEI_ETH_PRIVATE_KEY or PRIVATE_KEY env var must be set"
            )

        self._w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        if not self._w3.is_connected():
            raise RuntimeError(f"Cannot connect to chain at {rpc_url}")

        derived_account = account or self._w3.eth.account.from_key(private_key).address
        self._account     = Web3.to_checksum_address(derived_account)
        self._private_key = private_key
        self._chain_id    = self._w3.eth.chain_id
        self._gas_price   = _GAS_PRICE_WEI
        self._lock        = threading.Lock()
        self._nonce       = self._w3.eth.get_transaction_count(self._account)
        self._credit_ledger = None
        if credit_ledger_address:
            self._credit_ledger = self._w3.eth.contract(
                address=Web3.to_checksum_address(credit_ledger_address),
                abi=_CREDIT_LEDGER_ABI,
            )

        log.info(
            "ChainClient connected: account=%s chain_id=%d nonce=%d",
            self._account, self._chain_id, self._nonce,
        )

    # ── Public API ───────────────────────────────────────────────────────────

    def anchor(self, event_type: str, decision_hash: str) -> Optional[str]:
        """
        Write ``event_type:decision_hash`` to the chain as tx calldata.

        Returns the transaction hash (hex string) on success, None on failure.
        The call is synchronous but does *not* wait for confirmation —
        the tx is submitted and the nonce is advanced immediately.
        """
        try:
            payload = f"{event_type}:{decision_hash}".encode("utf-8")
            with self._lock:
                tx = {
                    "from":     self._account,
                    "to":       _LOG_SINK,
                    "value":    0,
                    "gas":      50_000,
                    "gasPrice": self._gas_price,
                    "nonce":    self._nonce,
                    "chainId":  self._chain_id,
                    "data":     "0x" + payload.hex(),
                }
                signed   = self._w3.eth.account.sign_transaction(tx, self._private_key)
                tx_bytes = getattr(signed, "raw_transaction", None) or signed.rawTransaction
                tx_hash  = self._w3.eth.send_raw_transaction(tx_bytes)
                self._nonce += 1

            tx_hex = _normalize_tx_hash(tx_hash)
            log.debug("anchored %s:%s… → tx=%s…", event_type, decision_hash[:12], tx_hex[:16])
            return tx_hex

        except Exception:
            log.exception("chain anchor failed (hash=%s…)", decision_hash[:12])
            return None

    def award_credits(self, ev_id: str, kwh: float, station_id: str = "") -> dict:
        """Award redeemable V2G credits for discharged energy.

        Returns a local settlement dict even when no contract is configured.
        If ``AEI_CREDIT_LEDGER_ADDRESS`` is set, the award is also submitted
        to the on-chain `CreditLedger` contract.
        """
        kwh_milli = max(0, int(round(float(kwh) * 1000)))
        credits = int(float(kwh) / _KWH_PER_CREDIT)
        result = {
            "ev_id": ev_id,
            "station_id": station_id,
            "kwh": round(float(kwh), 6),
            "credits_awarded": credits,
            "tx_hash": None,
            "ledger_mode": "local_only",
            "ledger_status": "skipped" if credits <= 0 else "local_only",
            "block_number": None,
            "transaction_submission_latency_ms": None,
            "transaction_confirmation_latency_ms": None,
            "transaction_total_latency_ms": None,
        }
        if self._credit_ledger is None or credits <= 0:
            return result
        receipt = self._send_contract_tx(
            self._credit_ledger.functions.award_credits(ev_id, station_id, kwh_milli)
        )
        result["ledger_mode"] = "on_chain"
        if receipt:
            result["tx_hash"] = receipt["tx_hash"]
            result["ledger_status"] = receipt["status"]
            result["block_number"] = receipt["block_number"]
            result["transaction_submission_latency_ms"] = receipt["transaction_submission_latency_ms"]
            result["transaction_confirmation_latency_ms"] = receipt["transaction_confirmation_latency_ms"]
            result["transaction_total_latency_ms"] = receipt["transaction_total_latency_ms"]
        else:
            result["ledger_status"] = "failed"
        return result

    def redeem_credits(self, ev_id: str, amount: int) -> Optional[str]:
        if self._credit_ledger is None:
            return None
        return self._send_contract_tx(self._credit_ledger.functions.redeem_credits(ev_id, int(amount)))

    def get_balance(self, ev_id: str) -> Optional[int]:
        if self._credit_ledger is None:
            return None
        try:
            return int(self._credit_ledger.functions.get_balance(ev_id).call())
        except Exception:
            log.exception("credit balance query failed (ev_id=%s)", ev_id)
            return None

    def _send_contract_tx(self, fn) -> Optional[dict]:
        try:
            total_start = time.perf_counter()
            with self._lock:
                tx = fn.build_transaction({
                    "from": self._account,
                    "gas": 500_000,
                    "gasPrice": self._gas_price,
                    "nonce": self._nonce,
                    "chainId": self._chain_id,
                })
                signed = self._w3.eth.account.sign_transaction(tx, self._private_key)
                tx_bytes = getattr(signed, "raw_transaction", None) or signed.rawTransaction
                submit_start = time.perf_counter()
                tx_hash = self._w3.eth.send_raw_transaction(tx_bytes)
                submit_end = time.perf_counter()
                self._nonce += 1
            confirm_start = time.perf_counter()
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=_TX_TIMEOUT_SECONDS)
            confirm_end = time.perf_counter()
            return {
                "tx_hash": _normalize_tx_hash(tx_hash),
                "status": "success" if receipt.status == 1 else "failed",
                "block_number": int(receipt.blockNumber),
                "transaction_submission_latency_ms": round((submit_end - submit_start) * 1000.0, 6),
                "transaction_confirmation_latency_ms": round((confirm_end - confirm_start) * 1000.0, 6),
                "transaction_total_latency_ms": round((confirm_end - total_start) * 1000.0, 6),
            }
        except Exception:
            log.exception("credit ledger transaction failed")
            return None

    @property
    def connected(self) -> bool:
        try:
            return self._w3.is_connected()
        except Exception:
            return False


def build_from_env() -> Optional[ChainClient]:
    """
    Build a ChainClient from environment variables.
    Returns None (silently) when web3 is not installed or env vars are absent.
    Safe to call at import time.
    """
    if not _WEB3_AVAILABLE:
        log.warning("web3 not installed — on-chain anchoring disabled")
        return None
    if not _PRIVATE_KEY:
        log.debug("AEI_ETH_PRIVATE_KEY or PRIVATE_KEY not set — local-only mode")
        return None
    try:
        return ChainClient()
    except Exception as exc:
        log.warning("ChainClient init failed (%s) — falling back to local-only", exc)
        return None
