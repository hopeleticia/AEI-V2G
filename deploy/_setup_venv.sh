#!/bin/bash
set -e

# ── Fix DNS (persists across sessions in this script's execution) ──────────
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf > /dev/null
# Make systemd-resolved use these nameservers on future boots too
sudo mkdir -p /etc/systemd/resolved.conf.d
printf '[Resolve]\nDNS=8.8.8.8 1.1.1.1\nFallbackDNS=9.9.9.9\n' | sudo tee /etc/systemd/resolved.conf.d/dns.conf > /dev/null

# ── Create venv and install ────────────────────────────────────────────────
VENV="$HOME/aei-venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q PyYAML paho-mqtt 'web3>=6.0.0' 2>&1 | tail -3
"$VENV/bin/python3" -c "import yaml; print('yaml_ok')"
"$VENV/bin/python3" -c "import paho.mqtt.client; print('paho_ok')"
"$VENV/bin/python3" -c "import web3; print('web3_ok')"
echo "VENV_READY"
