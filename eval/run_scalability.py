from __future__ import annotations

import json

from integration.coordinator import run


def main() -> None:
    metrics = run("config/corridor_config.yaml", 7200, "reports/scalability_3_station.json")["metrics"]
    print(json.dumps({"stations": 3, "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
