# ISAC-V2G / AEI-V2G Project Handoff

This document is the practical handoff for the current AEI-V2G work. It explains what the project is trying to prove, what has already been implemented, how to reproduce the experiments, where the results are stored, and what still needs to be done.

## Project Goal

AEI-V2G tests whether pre-arrival sensing can improve Vehicle-to-Grid energy management.

The core idea is:

1. A roadside ISAC/RSU component detects an approaching EV before it plugs in.
2. The system estimates useful pre-arrival features such as distance, speed, ETA, and a SoC proxy.
3. A decision engine routes the EV to a charging station and reserves capacity before arrival.
4. During grid stress, connected eligible EVs can discharge energy back to the grid through V2G dispatch.
5. V2G participants receive credit points, and energy/credit events are logged for auditability.

The main research claim is not only "V2G can reduce grid stress." The added contribution is that ISAC-based pre-arrival knowledge gives the scheduler earlier information, so it can act before the EV physically reaches the charger.

## What Is Implemented Now

The current repo has a working simulation pipeline for:

- RSU/ISAC-style EV detection and feature generation.
- Pre-arrival ETA estimation and station routing.
- Pre-arrival station reservation.
- Per-EV SoC tracking.
- A calibrated regression-style SoC proxy estimator.
- Three charging stations along a corridor.
- V2G dispatch during high grid stress.
- Battery safety constraints for V2G.
- Credit-point settlement records for V2G discharge.
- Local hash-chain audit logs.
- Purechain deployment support for the credit ledger smart contract.
- Docker-based experiment execution.
- Docker-based distributed component testing.
- A benchmark implementation based on the Fakhrooeian and Pitz V2G scheduling paper.

## What Is Simulated vs Real

This is important for defending the work honestly.

| Area | Current status |
|---|---|
| CAISO grid demand | Real grid-load profile used to shape grid stress. |
| EV arrivals | Simulated digital-twin traffic, not from a real EV arrival dataset. |
| RSU/ISAC sensing | Simulation-level sensing abstraction, not raw RF waveform processing. |
| SoC proxy | Calibrated regression-style estimator from simulated sensing features, not a trained field model. |
| Charging stations | Simulated corridor stations with configured slots and power limits. |
| V2G dispatch | Implemented in the simulator and settlement logs. |
| Blockchain audit | Local hash-chain works now. |
| Purechain on-chain credits | Deployment support exists; needs private key, deployment, and rerun to collect on-chain transaction results. |
| Raspberry Pi deployment | Docker containers currently represent the real-world components; physical Pis are not required for the present experiments. |

## Data Inputs

The full journal-style experiment uses a mix of real grid data and simulated EV/station behavior.

Real input:

- CAISO demand profile:
  - `data/grid_profiles/caiso_2024-05-01_2024-05-07.csv`
  - Configured through `config/corridor_config.yaml`.
  - Used to create a realistic daily grid-demand and grid-stress shape.

Simulated inputs:

- EV arrivals.
- EV speeds and positions along the corridor.
- RSU sensing observations.
- Station queues.
- V2G participation and discharge behavior.
- WAN outage and degraded ISAC scenario conditions.

The CAISO data gives the grid side of the experiment a realistic load profile.

## System Components

The project can be described as five main components.

| Component | Purpose | Main files |
|---|---|---|
| RSU / ISAC sensing | Detect approaching EVs and estimate pre-arrival features. | `sim/rsu_model.py`, `sensing/soc_proxy.py` |
| Station model | Track station slots, queues, reservations, charging, and completion. | `sim/station_model.py`, `sim/entities.py` |
| Grid model | Convert CAISO demand, charging load, and V2G relief into grid stress. | `eval/run_journal_study.py`, `config/corridor_config.yaml` |
| Decision engine / LAVA | Route EVs, reserve slots, and decide V2G dispatch. | `scheduling/lava_scheduler.py`, `integration/coordinator.py`, `integration/v2g_dispatcher.py` |
| Trust / blockchain layer | Log decisions, settlements, and credit awards. | `logging_layer/chain_client.py`, `contracts/CreditLedger.sol` |

## Docker Modes

There are two Docker modes. They answer different questions.

| Docker profile | What it does | Main purpose | Output |
|---|---|---|---|
| `experiment` | Runs the full 24-hour by 5-scenario journal-style experiment inside Docker. | Paper-facing performance evaluation. | `reports/docker_experiment/` |
| `local` | Runs separate Docker containers for the system roles. | Shows the system can be split into RSU, station, grid, and decision-engine components. | `reports/pi*_metrics.json`, `data/pi*_chain.jsonl` |

Use `experiment` for the main result tables and figures. Use `local` when you want to demonstrate distributed component separation.

## Charging Station Setup

The corridor has three simulated charging stations.

| Station | Corridor location | Active charging slots | Max station power |
|---|---:|---:|---:|
| `station_a` | 8 km from the corridor start | 6 slots | 360 kW |
| `station_b` | 24 km from the corridor start | 7 slots | 420 kW |
| `station_c` | 41 km from the corridor start | 5 slots | 300 kW |

How to interpret this:

- The location is distance from the start of the simulated road corridor.
- Slots mean how many EVs can actively charge at the same time.
- If all slots are occupied, arriving EVs enter a queue.
- Max station power caps total station load.
- Each active EV contributes up to about 55 kW.
- These power levels represent moderate DC fast-charging stations, not Level 1 or Level 2 home chargers.

## Scenario Definitions

The full experiment evaluates five scenarios.

| Scenario | Meaning |
|---|---|
| `weekday_nominal` | Normal intercity weekday with ordinary morning/evening demand variation. |
| `evening_peak_v2g` | High evening grid stress where V2G should help reduce peak pressure. |
| `event_surge` | Concert/event-style surge with many more EV arrivals than normal; intentionally stresses station capacity. |
| `rural_degraded_isac` | Reduced sensing coverage, representing terrain, rain, sparse RSUs, or weaker roadside sensing. |
| `wan_outage_edge_only` | External WAN/cloud reporting is unavailable, but local edge control continues. |

The `event_surge` scenario is expected to produce queues. That does not mean AEI-V2G failed. It means the scenario exceeded station capacity, so scheduling can reduce grid stress and route vehicles better, but it cannot create extra chargers.

## Baseline Used

The main AEI-V2G experiment uses an internal reactive baseline.

This baseline represents a simpler system where EVs are handled after arrival, without:

- ISAC-based pre-arrival knowledge.
- Pre-arrival slot reservation.
- Proactive station routing.
- Managed V2G grid relief.

This baseline is useful for showing what the AEI-V2G control logic adds. It is not an external paper baseline.

## Main Metrics

| Metric | What it means | Why it matters |
|---|---|---|
| Served ratio | Percentage of generated EV demand that was served. | Measures charging service quality. |
| Scheduling delay / latency | Time taken by the decision engine to route or dispatch. | Shows responsiveness of the control loop. |
| Grid-stress reduction | Reduction in high-stress grid behavior compared with the reactive baseline. | Measures grid support. |
| High-stress minutes | Minutes where grid stress is at or above the stress threshold. | Easier to explain than a raw stress index. |
| Charging completion rate | Percentage of EVs that completed their charging requirement. | Measures whether service was actually delivered. |
| Station load | Average kW handled by each station. | Shows load distribution across stations. |
| Peak queue depth | Worst backlog at each station. | Reveals capacity bottlenecks. |
| V2G participation rate | Share of eligible/active opportunities that used V2G. | Shows incentive-driven participation and dispatch usage. |
| V2G supplied energy | Energy discharged from EVs back to the grid. | Quantifies grid support. |
| Credits awarded | Credit points given for V2G discharge. | Connects energy support to incentives. |
| Chain validity | Whether local audit records validate. | Confirms decision trace integrity. |

## Core Comparison Metrics

When comparing AEI-V2G with existing works, focus on metrics that show what the whole system adds beyond ordinary EV charging, smart charging, or V2G scheduling.

| Comparison area | Metrics to look for | What it proves |
|---|---|---|
| Charging service | Served ratio, charging completion rate, waiting time, peak queue depth | The system still serves EVs while supporting the grid. |
| Grid support | Peak load, high-stress minutes, grid-stress reduction, V2G supplied kWh | V2G dispatch reduces pressure on the grid. |
| Scheduling benefit | Reactive baseline vs proactive routing/reservation, reservation success, queue reduction | Pre-arrival scheduling is better than waiting until plug-in. |
| ISAC benefit | With ISAC vs without ISAC, ETA accuracy, SoC proxy error, sensing coverage | Roadside sensing adds useful early information. |
| V2G participation | V2G invitations, acceptances, participation rate, credits awarded | Incentives can encourage EV owners to participate in V2G. |
| Trust and blockchain | Chain validity, transaction success count, transaction failure count, settlement delay | Energy and credit records can be audited transparently. |
| System responsiveness | Scheduler latency, edge continuity during WAN outage | The control loop can react quickly and continue locally. |

The strongest comparison set for a paper would include:

1. A reactive baseline with no pre-arrival sensing.
2. A forecast-only smart charging baseline.
3. A V2G scheduling baseline without ISAC.
4. A proactive/oracle scheduling upper bound, if available.
5. The full AEI-V2G system.

The current repo already reports served ratio, completion behavior, queues, grid-stress reduction, V2G supplied energy, V2G participation, scheduler latency, and chain validity. The two comparison metrics that still need stronger evidence are true SoC estimation error against measured battery data and actual Purechain transaction results after deployment.

## Current Full Experiment Outputs

The current main report folder is:

```text
reports/docker_experiment/
```

Important files:

| File | Meaning |
|---|---|
| `scenario_comparison.csv` | Main scenario-level metrics table. |
| `*_detail.json` | Detailed per-scenario summary. |
| `*_trace.csv` | Time-series trace for each scenario. |
| `*_chain.jsonl` | Hash-chain audit records for each scenario. |
| `VALIDATION_DEFENSE.md` | Validation summary for the experiment artifacts. |
| `FIGURES.md` | Index of generated plots. |
| `figures/` | Plot images. |

Current figures:

| Figure | File | What it shows |
|---|---|---|
| 1 | `fig_01_scenario_performance.png` | Served ratio, grid-stress reduction, and forecast accuracy. |
| 2 | `fig_02_latency_profile.png` | LAVA P95 and max decision latency. |
| 3 | `fig_03_v2g_energy_revenue.png` | V2G supplied energy and settlement value. |
| 4 | `fig_04_station_avg_load.png` | Average load at each station. |
| 5 | `fig_05_station_peak_queue.png` | Peak queue depth at each station. |
| 6 | `fig_06_grid_stress_minutes.png` | Reactive baseline vs AEI-V2G high-stress minutes. |
| 7 | `fig_07_event_surge_timeline.png` | Final 15-minute event-surge grid response and V2G dispatch. |
| 8 | `fig_08_charging_completion_rate.png` | Charging completion rate and EV counts. |
| 9 | `fig_09_v2g_participation_rate.png` | V2G participation and supplied energy. |
| 10 | `fig_10_v2g_discharge_credits.png` | Accepted V2G discharge events and credits awarded. |

## Current Result Snapshot

The latest full 24-hour by 5-scenario Docker experiment in `reports/docker_experiment/` produced:

| Scenario | Spawned EVs | Served EVs | Served ratio | Grid-stress reduction | V2G supplied | V2G revenue | Chain valid |
|---|---:|---:|---:|---:|---:|---:|---|
| Weekday nominal | 621 | 495 | 96.68% | 64.60% | 1630.467 kWh | 1021.50 | true |
| Evening peak V2G | 775 | 628 | 97.21% | 29.95% | 2055.267 kWh | 1310.18 | true |
| Event surge | 1278 | 734 | 68.66% | 62.28% | 2411.400 kWh | 1527.14 | true |
| Rural degraded ISAC | 688 | 548 | 96.48% | 60.21% | 1804.467 kWh | 1138.28 | true |
| WAN outage edge-only | 724 | 575 | 96.48% | 41.12% | 1912.600 kWh | 1214.73 | true |

Interpretation:

- AEI-V2G reduces high-stress grid minutes in every scenario.
- Normal weekday operation is manageable.
- Evening peak remains difficult because grid demand is already high.
- Event surge is the hardest service scenario because EV arrivals exceed station capacity.
- Station B carries the highest load partly because it has the highest configured capacity.
- The scheduler is computationally lightweight in simulation, but this is not the same as physical end-to-end latency.
- Local audit-chain validation passes.

## How To Run The Full Journal-Style Docker Experiment

Run these commands from the repo root.

```powershell
cd D:\CODE\AEI_V2G
docker compose -f docker-compose.pi.yml --profile experiment down
$env:AEI_DURATION_SECONDS=86400
docker compose -f docker-compose.pi.yml --profile experiment up --build
```

Then validate and regenerate plots:

```powershell
.\.aei\Scripts\python.exe -m eval.validate_journal_results `
  --report-dir reports\docker_experiment `
  --output reports\docker_experiment\VALIDATION_DEFENSE.md

.\.aei\Scripts\python.exe -m eval.plot_journal_results `
  --report-dir reports\docker_experiment `
  --output-dir reports\docker_experiment\figures
```

Expected output folder:

```text
reports/docker_experiment/
```

## How To Run The Distributed Component Docker Test

This mode shows that the system can be split into component roles.

```powershell
cd D:\CODE\AEI_V2G
docker compose -f docker-compose.pi.yml --profile local down
$env:AEI_DURATION_SECONDS=3600
docker compose -f docker-compose.pi.yml --profile local up --build
```

Expected outputs:

| Output | Role |
|---|---|
| `reports/pi1_metrics.json` | LAVA decision engine |
| `reports/pi2_metrics.json` | Station validator for station A/B |
| `reports/pi3_metrics.json` | Station validator for station C |
| `reports/pi5_metrics.json` | RSU observer |
| `reports/pi6_metrics.json` | Grid observer |
| `data/pi*_chain.jsonl` | Per-role audit logs |

Use this mode for architecture demonstration. Use the `experiment` profile for paper-facing scenario results.

## Blockchain and Purechain Status

The repo now has two layers of trust logging.

1. Local audit layer:
   - Works now.
   - Writes hash-chain JSONL logs such as `*_chain.jsonl`.
   - Used for decision trace validation.

2. Purechain credit ledger:
   - Smart contract exists at `contracts/CreditLedger.sol`.
   - Python client exists at `logging_layer/chain_client.py`.
   - Docker env wiring exists in `docker-compose.pi.yml`.
   - Deployment script is available.
   - Needs your private key and deployed contract address before on-chain credit results are produced.

Purechain is gas-free, so do not present blockchain overhead as Ether/gas cost. For Purechain, the useful blockchain metrics are:

- Settlement latency.
- Successful transaction count.
- Failed transaction count.
- Confirmation reliability.
- Audit completeness.
- Credit award correctness.

### Purechain Deployment Steps

Create or update `.env` with:

```text
AEI_RPC_URL=https://purechainnode.com:8547
AEI_ETH_CHAIN_ID=900520900520
AEI_ACCOUNT=
AEI_PRIVATE_KEY=
AEI_CREDIT_LEDGER_ADDRESS=
```

You will fill in the private key yourself.

Deploy the contract:

```powershell
npm run deploy:credit-ledger:purechain
```

After deployment, the repo should update:

- `.env`
- `deployments/purechain_credit_ledger.json`
- `deploy/PURECHAIN_CREDIT_LEDGER.md`

Then rerun the full Docker experiment. New runs should include credit ledger transaction counts and transaction hashes when the Purechain client is configured successfully.

## Benchmark Implementation Status

The benchmark folder is:

```text
Benchmark/
```

Main files:

| File | Purpose |
|---|---|
| `Benchmark/run_fakhrooeian_pitz.py` | Runs the benchmark scheduling replication. |
| `Benchmark/plot_fakhrooeian_pitz.py` | Generates benchmark plots. |
| `Benchmark/paper_reference_values.json` | Stores paper reference values used for comparison. |

Preferred benchmark figure:

```text
reports/benchmark_fakhrooeian_pitz/figures/fig_05_load_profile_pattern_reconstruction.png
```

The benchmark is a scheduling-level replication of the Fakhrooeian and Pitz paper, not an exact DIgSILENT PowerFactory feeder replication. It uses the paper's scenario structure, stochastic EV behavior, and available equations/parameters where possible, but it does not use the original factory feeder model or proprietary feeder data.

Use the benchmark to argue:

- The reference paper shows that scheduling and operator control reduce peak load.
- Our work builds on that idea by adding pre-arrival ISAC sensing, station reservation, corridor routing, V2G incentives, and auditability.

## What To Be Careful Saying

Use these careful phrasings:

- "Simulation-level ISAC abstraction" instead of "real ISAC waveform implementation."
- "Calibrated regression-style SoC proxy" instead of "trained SoC prediction model."
- "Docker containers represent system components" instead of "Docker replaces Raspberry Pis" when speaking formally.
- "Local hash-chain audit currently works; Purechain deployment is configured but must be run" instead of "blockchain is fully deployed."
- "Event surge exceeds station capacity" instead of "AEI-V2G failed in event surge."
- "Scheduler compute latency" instead of "full deployment latency" for the current latency plot.

## Known Limitations

- EV arrival behavior is generated by the simulator, not currently replayed from ACN-Data or another EV arrival dataset.
- ISAC sensing is modeled from features such as range, speed, RSSI-like strength, and Doppler-like shift; raw RF signal processing is not implemented.
- SoC proxy is calibrated, not trained on measured battery data.
- The reactive baseline is internal and simple.
- On-chain Purechain credit metrics require contract deployment and rerunning the experiment.

## Recommended Next Steps

1. Deploy `CreditLedger.sol` to Purechain and rerun the full Docker experiment.
2. Confirm that `scenario_comparison.csv` includes on-chain credit transaction counts and failures.
3. Add a figure or table for:
   - V2G discharge events.
   - Credits awarded.
   - Purechain transaction success/failure.
4. Improve the event-surge case by testing additional station capacity, stronger pre-arrival diversion, or demand throttling.
5. Add a real EV charging arrival dataset, such as ACN-Data, if the paper needs stronger empirical EV behavior.
6. Separate scheduler compute latency from communication latency, blockchain latency, and end-to-end control latency.
7. Keep the benchmark section framed as scheduling-level replication, not an exact feeder reproduction.

## Quick File Map

| Path | Why it matters |
|---|---|
| `config/corridor_config.yaml` | Main corridor, station, grid-profile, and scenario configuration. |
| `eval/run_journal_study.py` | Main full-experiment runner. |
| `eval/plot_journal_results.py` | Generates the journal-style figures. |
| `eval/validate_journal_results.py` | Validates experiment artifacts. |
| `integration/coordinator.py` | Coordinates RSU, station, scheduler, V2G, and logging behavior. |
| `integration/v2g_dispatcher.py` | Applies V2G discharge and credit settlement. |
| `sensing/soc_proxy.py` | SoC proxy inference from ISAC-style features. |
| `sim/rsu_model.py` | RSU detection and pre-arrival feature generation. |
| `sim/station_model.py` | Charging station queues, slots, reservations, and charging updates. |
| `scheduling/lava_scheduler.py` | Main LAVA routing and dispatch logic. |
| `logging_layer/chain_client.py` | Local/Purechain credit ledger client. |
| `contracts/CreditLedger.sol` | Smart contract for credit awards and redemption. |
| `docker-compose.pi.yml` | Docker profiles for full experiment and distributed component mode. |
| `reports/docker_experiment/` | Current main experiment outputs. |
| `Benchmark/` | Benchmark implementation. |
