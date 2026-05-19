from __future__ import annotations

import argparse
import json

from integration.coordinator import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/corridor_config.yaml")
    parser.add_argument("--duration", type=int, default=86400)
    parser.add_argument("--output", default="reports/baseline_comparison.json")
    args = parser.parse_args()
    report = run(args.config, args.duration, args.output)
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
