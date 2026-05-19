"""
eval/run_comparison.py
======================
Head-to-head comparison of LAVA (heuristic baseline) vs DRQN (learned policy)
over identical simulation episodes.

What this produces
------------------
  reports/comparison/
    comparison_summary.json   — side-by-side metric table (paper Table 3)
    drl_training_curve.json   — per-episode reward + loss (paper Fig. convergence)
    drl_checkpoint.pt         — saved DRL weights after training
    lava_episodes.json        — raw per-episode LAVA metrics
    drl_train_episodes.json   — raw per-episode DRL metrics (training phase)
    drl_eval_episodes.json    — raw per-episode DRL metrics (evaluation phase)

How the comparison works
------------------------
Phase 1 — LAVA reference (N_EVAL episodes):
    Run LAVA on N_EVAL episodes with the same config and seeds.
    Record per-episode: grid stress peaks, wait time, v2g revenue, evs_served.

Phase 2 — DRL training (N_TRAIN episodes):
    Run DRL with exploration (epsilon-greedy) for N_TRAIN episodes.
    Log per-episode: cumulative reward, mean loss, epsilon.

Phase 3 — DRL evaluation (N_EVAL episodes):
    Freeze DRL weights (eval_mode=True, epsilon=0).
    Run same N_EVAL episodes as Phase 1.
    Record identical metrics.

Phase 4 — Comparison table:
    Compute PAR proxy, TEC proxy, scheduling lag, SoC satisfaction ratio,
    sensing gain delta-J = reward_DRL_eval - reward_LAVA for each episode.

Seeding
-------
Each episode uses a different YAML seed override so both schedulers see the
same sequence of EV arrivals (fair comparison).  Seeds are drawn from a fixed
list so the experiment is reproducible.

Research objective mapping
--------------------------
  Obj-9   PAR, TEC, SoC satisfaction, scheduling lag, sensing gain delta-J.
  Obj-10  ISAC-aided DRL vs LAVA baseline under same simulation conditions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on the path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from integration.coordinator import run as coordinator_run
from scheduling.lava_scheduler import LAVAScheduler
from scheduling.drl_scheduler import DRLScheduler

# ── Experiment parameters (override via CLI) ──────────────────────────────────
DEFAULT_CONFIG   = "config/corridor_config.yaml"
DEFAULT_DURATION = 3600          # seconds per episode (60 ticks × 60 s)
N_TRAIN          = 200           # DRL training episodes
N_EVAL           = 30            # evaluation episodes for both schedulers
OUTPUT_DIR       = "reports/comparison"
DRL_CHECKPOINT   = "reports/comparison/drl_checkpoint.pt"

# Fixed seeds for reproducible per-episode EV generation.
EPISODE_SEEDS = list(range(1000, 1000 + max(N_TRAIN, N_EVAL) + 50))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _write_config_with_seed(base_config: dict, seed: int, tmp_path: str) -> str:
    """Write a copy of the corridor config with a different seed."""
    cfg = dict(base_config)
    cfg["seed"] = seed
    with open(tmp_path, "w", encoding="utf-8") as fh:
        yaml.dump(cfg, fh)
    return tmp_path


def _episode_metrics(report: dict) -> dict:
    """Extract comparable metrics from a coordinator run report."""
    samples = report.get("full_samples") or report.get("samples", [])
    m = report.get("metrics", {})

    # Grid stress peaks (PAR proxy — count of ticks above critical threshold 0.8)
    stress_peaks = sum(1 for s in samples if s.get("grid_stress", 0) >= 0.8)
    total_ticks  = max(1, len(samples))

    # Total energy cost proxy (sum of tariff × load × tick_hours)
    tec = sum(
        s.get("actual_kw", 0) * 0.35 * (1 / 60)   # ~0.35 $/kWh × hour-fraction
        for s in samples
    )

    # Mean scheduling lag proxy.
    # LAVA/DRL with ISAC sensing routes EVs before plug-in → lag ≈ 0.
    # A pure reactive system would have lag = one full tick (60 s).
    # We compute: mean decision latency (already measured in ms).
    latencies = [s.get("latency_ms", 0) for s in samples if s.get("latency_ms")]
    mean_latency_ms = sum(latencies) / max(1, len(latencies))

    # V2G revenue.
    v2g_revenue = sum(s.get("v2g_revenue", 0) for s in samples)

    # V2G utilisation.
    v2g_util = m.get("v2g_utilization_pct", 0.0)

    # EVs served.
    evs_served = m.get("evs_served", 0)

    # Grid stress reduction (from existing metrics).
    stress_reduction = m.get("grid_stress_reduction_pct", 0.0)

    return {
        "stress_peaks":       stress_peaks,
        "par_proxy":          stress_peaks / total_ticks,
        "tec_proxy":          round(tec, 4),
        "mean_latency_ms":    round(mean_latency_ms, 3),
        "v2g_revenue":        round(v2g_revenue, 4),
        "v2g_util_pct":       v2g_util,
        "evs_served":         evs_served,
        "stress_reduction_pct": stress_reduction,
        "sample_count":        len(samples),
    }


def _avg_metrics(episode_list: list[dict]) -> dict:
    if not episode_list:
        return {}
    keys = episode_list[0].keys()
    return {
        k: round(sum(ep[k] for ep in episode_list) / len(episode_list), 4)
        for k in keys
    }


# ── Phase runners ─────────────────────────────────────────────────────────────

def run_lava_phase(
    base_config: dict, config_path: str, duration: int, n_episodes: int, out_dir: Path
) -> tuple[list[dict], list[float]]:
    """Run LAVA for n_episodes.  Returns (per-episode metrics, per-episode reward proxy)."""
    scheduler = LAVAScheduler.from_yaml()
    results: list[dict] = []
    rewards: list[float] = []
    tmp_cfg = str(out_dir / "_tmp_cfg.yaml")

    for i in range(n_episodes):
        seed = EPISODE_SEEDS[i]
        cfg_path = _write_config_with_seed(base_config, seed, tmp_cfg)
        chain = str(out_dir / f"lava_ep{i:04d}_chain.jsonl")
        report = coordinator_run(
            cfg_path, duration,
            output_path=None,
            chain_path=chain,
            scheduler=scheduler,
        )
        ep = _episode_metrics(report)
        results.append(ep)
        # Reward proxy: V2G revenue − stress penalty
        rewards.append(ep["v2g_revenue"] - ep["par_proxy"] * 10.0)
        print(f"  LAVA ep {i+1:3d}/{n_episodes} | "
              f"stress_peaks={ep['stress_peaks']:3d} "
              f"tec={ep['tec_proxy']:.2f} "
              f"v2g_rev={ep['v2g_revenue']:.3f}")
    return results, rewards


def run_drl_training_phase(
    base_config: dict, config_path: str, duration: int, n_episodes: int, out_dir: Path,
    station_ids: list[str],
) -> tuple[DRLScheduler, list[dict]]:
    """Train DRL for n_episodes.  Returns (trained scheduler, training log)."""
    scheduler = DRLScheduler(station_ids, device="cpu", eval_mode=False)
    training_log: list[dict] = []
    tmp_cfg = str(out_dir / "_tmp_cfg.yaml")

    for i in range(n_episodes):
        seed = EPISODE_SEEDS[i]
        cfg_path = _write_config_with_seed(base_config, seed, tmp_cfg)
        chain = str(out_dir / f"drl_train_ep{i:04d}_chain.jsonl")

        scheduler.reset_episode()
        t0 = time.monotonic()
        report = coordinator_run(
            cfg_path, duration,
            output_path=None,
            chain_path=chain,
            scheduler=scheduler,
        )
        elapsed = time.monotonic() - t0
        ep = _episode_metrics(report)
        reward_proxy = ep["v2g_revenue"] - ep["par_proxy"] * 10.0
        training_log.append({
            "episode": i,
            "epsilon": round(scheduler.epsilon, 4),
            "train_steps": scheduler.train_steps,
            "reward_proxy": round(reward_proxy, 4),
            "elapsed_s": round(elapsed, 1),
            **ep,
        })
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  DRL train ep {i+1:4d}/{n_episodes} | "
                  f"ε={scheduler.epsilon:.3f} "
                  f"steps={scheduler.train_steps:5d} "
                  f"reward={reward_proxy:.3f} "
                  f"stress_peaks={ep['stress_peaks']}")

    return scheduler, training_log


def run_drl_eval_phase(
    base_config: dict, config_path: str, duration: int, n_episodes: int, out_dir: Path,
    trained_scheduler: DRLScheduler,
) -> list[dict]:
    """Evaluate frozen DRL for n_episodes (same seeds as LAVA phase)."""
    # Build a fresh eval-mode instance sharing weights.
    station_ids = trained_scheduler._station_ids
    eval_sched = DRLScheduler(station_ids, device="cpu", eval_mode=True)
    # Copy weights across by save/load.
    ckpt = str(out_dir / "drl_checkpoint.pt")
    trained_scheduler.save(ckpt)
    eval_sched.load(ckpt)

    results: list[dict] = []
    tmp_cfg = str(out_dir / "_tmp_cfg.yaml")

    for i in range(n_episodes):
        seed = EPISODE_SEEDS[i]           # same seeds as LAVA phase
        cfg_path = _write_config_with_seed(base_config, seed, tmp_cfg)
        chain = str(out_dir / f"drl_eval_ep{i:04d}_chain.jsonl")

        eval_sched.reset_episode()
        report = coordinator_run(
            cfg_path, duration,
            output_path=None,
            chain_path=chain,
            scheduler=eval_sched,
        )
        ep = _episode_metrics(report)
        results.append(ep)
        print(f"  DRL eval ep {i+1:3d}/{n_episodes} | "
              f"stress_peaks={ep['stress_peaks']:3d} "
              f"tec={ep['tec_proxy']:.2f} "
              f"v2g_rev={ep['v2g_revenue']:.3f}")

    return results


# ── Comparison table ──────────────────────────────────────────────────────────

def build_comparison_table(
    lava_metrics: list[dict],
    drl_eval_metrics: list[dict],
    lava_rewards: list[float],
    training_log: list[dict],
) -> dict:
    """Compute the summary comparison table for the paper."""
    lava_avg  = _avg_metrics(lava_metrics)
    drl_avg   = _avg_metrics(drl_eval_metrics)

    # Sensing gain delta-J: mean reward improvement DRL vs LAVA (Obj-9).
    drl_rewards = [
        ep["v2g_revenue"] - ep["par_proxy"] * 10.0
        for ep in drl_eval_metrics
    ]
    delta_j = round(
        sum(drl_rewards) / max(1, len(drl_rewards))
        - sum(lava_rewards) / max(1, len(lava_rewards)),
        4,
    )

    def pct_change(lava_val: float, drl_val: float) -> str:
        if abs(lava_val) < 1e-9:
            return "N/A"
        delta = (drl_val - lava_val) / abs(lava_val) * 100.0
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.1f}%"

    return {
        "lava": lava_avg,
        "drl_eval": drl_avg,
        "delta": {
            "par_proxy":          pct_change(lava_avg["par_proxy"],       drl_avg["par_proxy"]),
            "tec_proxy":          pct_change(lava_avg["tec_proxy"],        drl_avg["tec_proxy"]),
            "v2g_revenue":        pct_change(lava_avg["v2g_revenue"],      drl_avg["v2g_revenue"]),
            "stress_reduction":   pct_change(lava_avg["stress_reduction_pct"], drl_avg["stress_reduction_pct"]),
            "sensing_gain_delta_j": delta_j,
        },
        "training_summary": {
            "n_train_episodes":  len(training_log),
            "final_epsilon":     training_log[-1]["epsilon"] if training_log else None,
            "total_grad_steps":  training_log[-1]["train_steps"] if training_log else None,
            "reward_first_10":   round(
                sum(ep["reward_proxy"] for ep in training_log[:10]) / max(1, min(10, len(training_log))), 4
            ) if training_log else None,
            "reward_last_10":    round(
                sum(ep["reward_proxy"] for ep in training_log[-10:]) / max(1, min(10, len(training_log))), 4
            ) if training_log else None,
        },
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare LAVA vs DRQN scheduler on identical simulation episodes."
    )
    parser.add_argument("--config",   default=DEFAULT_CONFIG,   help="Corridor YAML config")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Seconds per episode")
    parser.add_argument("--n-train",  type=int, default=N_TRAIN,  help="DRL training episodes")
    parser.add_argument("--n-eval",   type=int, default=N_EVAL,   help="Evaluation episodes per scheduler")
    parser.add_argument("--out-dir",  default=OUTPUT_DIR,         help="Output directory")
    parser.add_argument("--lava-only", action="store_true",       help="Skip DRL, run LAVA only")
    parser.add_argument("--drl-only",  action="store_true",       help="Skip LAVA reference phase")
    parser.add_argument("--load-drl",  default=None,              help="Load DRL checkpoint, skip training")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_config = _load_config(args.config)
    station_ids = [row["id"] for row in base_config["stations"]]

    lava_metrics:    list[dict] = []
    lava_rewards:    list[float] = []
    drl_eval_metrics: list[dict] = []
    training_log:    list[dict] = []
    trained_scheduler: DRLScheduler | None = None

    # ── Phase 1: LAVA reference ───────────────────────────────────────────────
    if not args.drl_only:
        print(f"\n=== Phase 1: LAVA reference ({args.n_eval} episodes) ===")
        lava_metrics, lava_rewards = run_lava_phase(
            base_config, args.config, args.duration, args.n_eval, out_dir
        )
        (out_dir / "lava_episodes.json").write_text(
            json.dumps(lava_metrics, indent=2), encoding="utf-8"
        )
        print(f"  LAVA avg metrics: {json.dumps(_avg_metrics(lava_metrics), indent=4)}")

    if args.lava_only:
        print("\nLAVA-only mode: skipping DRL phases.")
        return

    # ── Phase 2: DRL training ─────────────────────────────────────────────────
    if args.load_drl:
        print(f"\n=== Skipping DRL training: loading checkpoint from {args.load_drl} ===")
        trained_scheduler = DRLScheduler(station_ids, device="cpu", eval_mode=False)
        trained_scheduler.load(args.load_drl)
    else:
        print(f"\n=== Phase 2: DRL training ({args.n_train} episodes) ===")
        trained_scheduler, training_log = run_drl_training_phase(
            base_config, args.config, args.duration, args.n_train, out_dir, station_ids
        )
        (out_dir / "drl_training_curve.json").write_text(
            json.dumps(training_log, indent=2), encoding="utf-8"
        )
        trained_scheduler.save(str(out_dir / "drl_checkpoint.pt"))
        print(f"  DRL checkpoint saved to {out_dir / 'drl_checkpoint.pt'}")

    # ── Phase 3: DRL evaluation ───────────────────────────────────────────────
    print(f"\n=== Phase 3: DRL evaluation ({args.n_eval} episodes) ===")
    drl_eval_metrics = run_drl_eval_phase(
        base_config, args.config, args.duration, args.n_eval, out_dir, trained_scheduler
    )
    (out_dir / "drl_eval_episodes.json").write_text(
        json.dumps(drl_eval_metrics, indent=2), encoding="utf-8"
    )

    # ── Phase 4: Comparison table ─────────────────────────────────────────────
    print("\n=== Phase 4: Comparison summary ===")
    summary = build_comparison_table(lava_metrics, drl_eval_metrics, lava_rewards, training_log)
    summary_path = out_dir / "comparison_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n--- LAVA vs DRL Comparison ---")
    print(f"{'Metric':<28} {'LAVA':>12} {'DRL':>12} {'Delta':>10}")
    print("-" * 64)
    for key in ["par_proxy", "tec_proxy", "v2g_revenue", "stress_reduction_pct", "evs_served"]:
        lv = summary["lava"].get(key, 0)
        dv = summary["drl_eval"].get(key, 0)
        dt = summary["delta"].get(key, "—")
        print(f"  {key:<26} {lv:>12.4f} {dv:>12.4f} {str(dt):>10}")
    print(f"\n  Sensing gain delta-J: {summary['delta']['sensing_gain_delta_j']}")
    ts = summary["training_summary"]
    print(f"  DRL training: {ts['n_train_episodes']} episodes, "
          f"{ts['total_grad_steps']} grad steps, "
          f"reward {ts['reward_first_10']} → {ts['reward_last_10']}")
    print(f"\nFull results written to: {out_dir}/")


if __name__ == "__main__":
    main()
