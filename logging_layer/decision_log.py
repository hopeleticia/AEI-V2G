from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class DecisionLog:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.previous_hash = self._load_last_hash()
        # Connect to the private Ethereum chain if credentials are available.
        # Falls back to local-only mode silently when web3 / env vars are absent.
        try:
            from logging_layer.chain_client import build_from_env
            self._chain = build_from_env()
        except Exception:
            self._chain = None

    def append(self, event_type: str, payload: dict) -> dict:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
            "previous_hash": self.previous_hash,
        }
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        record["hash"] = hashlib.sha256(encoded).hexdigest()

        # Anchor the hash on-chain before writing locally (best-effort).
        if self._chain is not None:
            tx_hash = self._chain.anchor(event_type, record["hash"])
            if tx_hash:
                record["tx_hash"] = tx_hash

        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        self.previous_hash = record["hash"]
        return record

    def _load_last_hash(self) -> str:
        if not os.path.exists(self.path):
            return "genesis"
        # Read the file in reverse chunks to find the last non-empty line without
        # scanning the entire file.  Each JSONL record is well under 64 KiB.
        chunk_size = 65536
        with open(self.path, "rb") as handle:
            handle.seek(0, 2)
            file_size = handle.tell()
            if file_size == 0:
                return "genesis"
            offset = max(0, file_size - chunk_size)
            handle.seek(offset)
            tail = handle.read().decode("utf-8", errors="replace")
        lines = [ln for ln in tail.splitlines() if ln.strip()]
        if not lines:
            return "genesis"
        return json.loads(lines[-1])["hash"]
