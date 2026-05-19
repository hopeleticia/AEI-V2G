from __future__ import annotations

import json
import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)

# ── MQTT topic constants ────────────────────────────────────────────────────
TOPIC_RSU_SENSE     = "aei/rsu/sense"
TOPIC_STATION_STATE = "aei/station/state"
TOPIC_GRID_STATE    = "aei/grid/state"
TOPIC_LAVA_ROUTE    = "aei/lava/route"
TOPIC_LAVA_V2G      = "aei/lava/v2g"
TOPIC_CHAIN_SYNC    = "aei/chain/sync"

try:
    import paho.mqtt.client as _mqtt  # type: ignore[import]
    _MQTT_AVAILABLE = True
except ImportError:
    _MQTT_AVAILABLE = False


class NodeBus:
    """
    Thin MQTT wrapper for AEI-V2G inter-node communication.

    Each Pi creates one NodeBus instance, subscribes to relevant topics,
    and publishes state / decisions.  Uses QoS-1 for all messages.
    Thread-safe: subscription handlers are called from the paho network thread.
    """

    def __init__(self, node_id: str, broker: str, port: int = 1883) -> None:
        if not _MQTT_AVAILABLE:
            raise RuntimeError(
                "paho-mqtt is required for distributed mode.  "
                "Run:  pip install paho-mqtt"
            )
        self.node_id = node_id
        self._lock = threading.Lock()
        self._handlers: dict[str, list[Callable]] = {}
        self._connected = threading.Event()

        self._client = _mqtt.Client(client_id=node_id, clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect_async(broker, port, keepalive=30)
        self._client.loop_start()

        if not self._connected.wait(timeout=15):
            self._client.loop_stop()
            raise RuntimeError(
                f"[{node_id}] MQTT connect timeout — "
                f"is broker running at {broker}:{port}?"
            )

    # ── paho callbacks ──────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc: int) -> None:
        if rc == 0:
            self._connected.set()
            with self._lock:
                for topic in self._handlers:
                    client.subscribe(topic, qos=1)
            log.info("[%s] connected to MQTT broker", self.node_id)
        else:
            log.error("[%s] MQTT connect failed rc=%d", self.node_id, rc)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            log.warning("[%s] malformed message on %s", self.node_id, msg.topic)
            return
        with self._lock:
            handlers = list(self._handlers.get(msg.topic, []))
        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                log.exception(
                    "[%s] handler error on topic %s", self.node_id, msg.topic
                )

    # ── public API ──────────────────────────────────────────────────────────

    def subscribe(self, topic: str, handler: Callable) -> None:
        """Register a callback for a topic.  Safe to call before connect."""
        with self._lock:
            self._handlers.setdefault(topic, []).append(handler)
        if self._connected.is_set():
            self._client.subscribe(topic, qos=1)

    def publish(self, topic: str, payload: dict) -> None:
        """Publish a dict as JSON with QoS-1."""
        self._client.publish(
            topic, json.dumps(payload, default=str), qos=1
        )

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
