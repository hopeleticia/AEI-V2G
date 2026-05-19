from __future__ import annotations

import json

from integration.coordinator import run


def main() -> None:
    results = {
        "full_lava": run("config/corridor_config.yaml", 7200, "reports/ablation_full_lava.json")["metrics"],
        "note": "Engine-specific ablations are represented by LAVA trace fields in the chain log for each decision.",
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
