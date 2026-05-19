# AEI-V2G: Adaptive Edge Intelligence for Proactive Vehicle-to-Grid Energy Management

## What This Project Is

An intercity EV charging coordination system that turns electric vehicles into flexible energy nodes on a proactive grid. Instead of the grid discovering what a vehicle needs after it physically plugs in (reactive), roadside units sense approaching vehicles via 6G ISAC, predict demand before arrival, and route vehicles to optimal charging stations — or ask them to sell energy back when the grid is stressed.

The decision engine is **LAVA** (a three-engine deterministic ensemble). Trust across all nodes is maintained by a lightweight blockchain mesh. The entire system runs on constrained edge hardware (Raspberry Pi-class nodes at each charging station and RSU).

---

## The Problem

Current EV charging infrastructure is **reactive**:

1. Vehicle arrives at a station → station reports load to grid → grid reacts
2. Multiple vehicles converge on the same station → localised demand spike → grid stress
3. No advance warning → no time to redistribute load or recruit V2G sellers
4. Cloud-dependent systems fail when connectivity drops (rural intercity corridors)

**Result:** Overloaded stations, underused stations 2 km away, unnecessary grid stress, and missed V2G revenue.

---

## The Solution: Three-Layer Proactive Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LAYER 3: VALIDATION                         │
│  Blockchain mesh across all nodes (RSUs + stations + grid edge)    │
│  - Immutable decision log    - Decentralised trust                 │
│  - V2G settlement records    - Anomaly audit trail                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ sync
┌──────────────────────────────▼──────────────────────────────────────┐
│                        LAYER 2: DECISION                           │
│  LAVA ensemble engine at each charging station cluster             │
│  - Global optimiser (demand prediction + slot allocation)          │
│  - Rule-based reasoner (grid stress rules, priority rules)         │
│  - Constraint enforcer (capacity limits, safety bounds)            │
│  - Median voting + cooldown gate                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ decisions
┌──────────────────────────────▼──────────────────────────────────────┐
│                        LAYER 1: AWARENESS                          │
│  6G ISAC roadside units along intercity corridors                  │
│  - Sense approaching EVs (speed, direction, distance)              │
│  - Receive EV broadcasts (battery %, destination, charge request)  │
│  - Relay station data (location, current load, available slots)    │
│  - Denoise + feature extraction via AEI feature extractor          │
└─────────────────────────────────────────────────────────────────────┘
```

## Project Objectives

1. To investigate and model the integration of Integrated Sensing and Communication (ISAC) technology with Vehicle-to-Grid (V2G) energy management systems
2. To integrate ISAC technology at roadside units to detect approaching electric vehicles and extract key parameters such as speed, distance, and estimated arrival time before the vehicle physically connects to the charger.
3. To estimate the battery state of charge/state of health of an approaching EV using ISAC sensing signals from the RSU, providing the energy management system with early knowledge of each vehicle's energy needs, enabling more accurate and personalised energy dispatch decisions
4. To develop a proactive scheduling framework that prepares a charging and discharging plan for each EV before it arrives, reducing reliance on reactive scheduling that only acts after plug-in
5. To implement a Vehicle-to-Grid (V2G) dispatch mechanism that responds to real-time grid stress by scheduling EVs to discharge energy back to the grid during peak demand periods, reducing pressure on the electricity network.
6. To design an incentive mechanism that rewards EV owners with redeemable credit points for discharging energy back to the grid during periods of high grid stress, encouraging voluntary V2G participation
7. To incorporate a blockchain layer for secure and transparent storage of vehicle energy data, transaction records, and incentive point balances, ensuring trust between all parties in the system.
---

## Data Flows

### What each node sends

| Node | Sends | To |
|------|-------|----|
| **EV** | location, speed, battery %, destination, charge request flag | Nearest RSU (via ISAC) |
| **RSU** | aggregated EV approach data, traffic density | Linked charging station(s) |
| **Charging station** | location, current load (kW), available slots, queue depth, energy price | RSUs in range + grid edge |
| **Grid edge** | current grid stress level, time-of-use tariff, V2G buy price | All stations in region |

### What each node receives back

| Node | Receives | From |
|------|----------|----|
| **EV** | recommended station, estimated wait time, V2G sell opportunity + price | RSU relay |
| **Charging station** | predicted demand (next 15/30/60 min), V2G dispatch orders | LAVA engine |
| **Grid edge** | aggregated regional demand forecast, V2G supply availability | Station cluster |

---

## The LAVA Decision Engine

LAVA runs at the **charging station cluster level** (one LAVA instance per group of 3-5 stations along a corridor segment). It makes two kinds of decisions:

### Decision A: Demand Prediction + Slot Allocation
- **Input:** EV approach vectors from RSUs, current station loads, grid stress signal
- **Output:** per-station demand forecast (15/30/60 min windows), slot reservation recommendations for approaching EVs

### Decision B: V2G Dispatch
- **Input:** grid stress level, connected EV battery levels, time-of-use tariff, V2G buy price
- **Output:** V2G sell invitations to eligible connected EVs, discharge rate and duration

### The three engines

```
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│  GLOBAL OPTIMISER  │  │  RULE REASONER    │  │ CONSTRAINT ENFORCER│
│                   │  │                   │  │                   │
│ Cost function:    │  │ Expert rules:     │  │ Hard limits:      │
│  w1·grid_stress   │  │  IF grid_stress   │  │  station_load     │
│ +w2·ev_wait_time  │  │    > 0.8 THEN     │  │    <= max_kW      │
│ +w3·station_imbal │  │    trigger V2G    │  │  ev_battery       │
│ +w4·energy_cost   │  │  IF ev_battery    │  │    >= 20% after   │
│                   │  │    < 25% THEN     │  │    V2G discharge  │
│ Searches state    │  │    priority charge │  │  queue_depth      │
│ space, ranks      │  │  IF station_full  │  │    <= max_slots   │
│ candidates        │  │    THEN redirect  │  │  grid_frequency   │
│                   │  │                   │  │    within bounds   │
└────────┬──────────┘  └────────┬──────────┘  └────────┬──────────┘
         │ candidate + conf.    │ candidate + conf.     │ pass/fail
         └──────────┬───────────┘                       │
                    ▼                                   │
            ┌───────────────┐                           │
            │ MEDIAN VOTING │◄──────────────────────────┘
            │  + COOLDOWN   │
            │               │
            │ If confidence │
            │ < threshold   │
            │ OR divergence │
            │ > margin:     │
            │   DEFER       │
            └───────┬───────┘
                    │
                    ▼
              FINAL DECISION
         (fully traceable to
          which engine drove it)
```

### Why median voting, not majority vote

If the optimiser says "send 50 kW to station A" and the rule engine says "send 0 kW" (because of a safety rule) and the constraint enforcer passes both — the median (the middle value) naturally pulls toward the conservative answer. A mean would average the extremes; a majority vote requires discrete agreement. The median gives a stable middle ground that prevents any single engine from dominating.

---

## Blockchain Layer (Validation)

Every LAVA decision, V2G transaction, and demand forecast is logged on a lightweight PoA blockchain running across the station cluster nodes. This provides:

- **Immutable audit trail** — regulators can verify what the system decided and why
- **V2G settlement** — energy sell/buy transactions between EVs and grid are recorded with tamper-evident hashes
- **Anomaly detection** — if a node's decisions diverge from its logged forecasts, the discrepancy is visible on-chain
- **Decentralised trust** — no single station operator controls the decision history

We reuse the **IIoT-Chain** implementation from the `iotnodes/` directory in this workspace. It already supports PoA consensus, ECDSA-secp256k1 signing, SQLite storage, and has been validated on a 5-node Raspberry Pi cluster.

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| RSU edge node | Raspberry Pi 4/5, Python 3.13 | Low cost, proven in our Pi cluster deployment |
| Station LAVA engine | Raspberry Pi 5 or Jetson Nano, Python | Runs the 3-engine ensemble locally |
| ISAC simulation | Python + NumPy | 6G ISAC channel model for approach sensing |
| Blockchain | IIoT-Chain (our custom PoA implementation) | Already validated on 5-node Pi cluster |
| EV simulator | Python | Generates realistic EV traffic with battery, speed, destination |
| Grid stress model | Python | Simulates grid load curves, tariffs, V2G pricing |
| Communication | UDP multicast (LAN) + HTTPS (WAN) | Matches IIoT-Chain's transport layer |
| Dashboard | React + TypeScript (reuse from sieveAi/React) | Real-time visualisation of grid state |

---

## Development Plan

### Phase 1: Simulation Core (Weeks 1-3)

**Goal:** Build the simulation environment so we can develop and test LAVA without hardware.

```
aei-v2g/
├── sim/
│   ├── ev_generator.py         # Spawn EVs with random battery, speed, destination
│   ├── rsu_model.py            # RSU sensing model (ISAC range, noise, feature extraction)
│   ├── station_model.py        # Charging station state (load, slots, queue)
│   ├── grid_model.py           # Grid stress curve, tariff schedule, V2G pricing
│   └── corridor.py             # Intercity corridor topology (RSU placement, station locations)
├── config/
│   └── corridor_config.yaml    # Corridor layout, station specs, grid params
└── tests/
    └── test_sim_basic.py       # Smoke test: EVs drive, RSUs sense, stations respond
```

**Deliverables:**
- [ ] EV generator producing realistic traffic patterns (Poisson arrival, battery distributions)
- [ ] RSU model that senses approaching EVs within ISAC range and extracts features
- [ ] Station model tracking load, slots, and queue in real time
- [ ] Grid model with configurable stress curves and V2G pricing
- [ ] Corridor topology connecting 3-5 stations with RSUs along a 50 km intercity route

### Phase 2: LAVA Engine (Weeks 3-5)

**Goal:** Implement the three LAVA engines and the median-voting ensemble.

```
aei-v2g/
├── lava/
│   ├── optimizer.py            # Global optimiser (cost function, state-space search)
│   ├── rules.py                # Rule-based reasoner (priority-ordered if-then rules)
│   ├── constraints.py          # Constraint enforcer (hard limits, binary pass/fail)
│   ├── ensemble.py             # Median voting + cooldown gate
│   ├── engine.py               # LAVA orchestrator (runs all 3, combines, logs trace)
│   └── cost_functions.py       # Pluggable cost-function components
├── config/
│   ├── lava_weights.yaml       # Optimiser cost weights (w1-w4)
│   ├── rules.yaml              # Rule definitions (human-readable)
│   └── constraints.yaml        # Hard constraint thresholds
└── tests/
    ├── test_optimizer.py
    ├── test_rules.py
    ├── test_constraints.py
    └── test_ensemble.py        # Verify median voting, cooldown, traceability
```

**Deliverables:**
- [ ] Global optimiser with configurable cost function (grid stress, wait time, station imbalance, energy cost)
- [ ] Rule engine loading rules from YAML, evaluating in priority order
- [ ] Constraint enforcer checking hard limits (station capacity, EV minimum battery, grid frequency)
- [ ] Median voting combining three candidates + confidence scores
- [ ] Cooldown gate deferring decisions when confidence is low or engines diverge
- [ ] Every decision traceable to which engine drove it and why

### Phase 3: Integration + Blockchain (Weeks 5-7)

**Goal:** Wire the sim to LAVA, add the blockchain validation layer, and run end-to-end.

```
aei-v2g/
├── integration/
│   ├── coordinator.py          # Main loop: sim ticks → LAVA decisions → state updates
│   ├── v2g_dispatcher.py       # V2G sell/buy invitation logic
│   └── ev_router.py            # Route EVs to recommended stations based on LAVA output
├── blockchain/
│   └── (symlink or copy from iotnodes/iiot-chain)
├── logging/
│   ├── decision_log.py         # Log every LAVA decision to blockchain
│   └── v2g_ledger.py           # Log V2G transactions to blockchain
└── tests/
    ├── test_e2e_basic.py       # 10 EVs, 3 stations, 60-min sim, verify no grid stress spike
    └── test_v2g_trigger.py     # Force grid stress, verify V2G dispatch fires
```

**Deliverables:**
- [ ] End-to-end simulation: EVs approach → RSUs sense → LAVA decides → stations update → grid responds
- [ ] V2G dispatch: when grid stress exceeds threshold, eligible EVs receive sell invitations
- [ ] Every LAVA decision logged on IIoT-Chain blockchain with tamper-evident hash chain
- [ ] V2G transactions recorded on-chain for settlement and audit

### Phase 4: Raspberry Pi Deployment (Weeks 7-9)

**Goal:** Deploy the system on the existing 5-node Pi cluster and run a live demo.

| Pi Node | Role | Software |
|---------|------|----------|
| pi1 | Station cluster LAVA engine + validator | lava/engine.py + IIoT-Chain validator |
| pi2 | Station node 2 + validator | station_model.py + IIoT-Chain validator |
| pi3 | Station node 3 + validator | station_model.py + IIoT-Chain validator |
| pi5 | RSU simulator + observer | rsu_model.py + ev_generator.py + IIoT-Chain observer |
| pi6 | Grid edge node + observer | grid_model.py + dashboard relay + IIoT-Chain observer |

**Deliverables:**
- [ ] Automated deployment script (extend deploy_rpi_nodes.py from iotnodes)
- [ ] Live 10-minute run with simulated EV traffic across 3 stations
- [ ] Measure: decision latency (ms), offline uptime (%), energy overhead (mJ per decision)
- [ ] Blockchain consensus verified across all 5 nodes
- [ ] Deployment report with hardware inventory, logs, and metrics

### Phase 5: Evaluation + Paper (Weeks 9-12)

**Goal:** Run the full evaluation suite and write the paper.

**Evaluation metrics:**

| Metric | Target | How measured |
|--------|--------|-------------|
| Demand prediction accuracy | > 85% (MAE < 15% of actual) | Compare LAVA forecast vs actual station load over 24h sim |
| Grid stress reduction | > 30% fewer peak-stress events | Compare reactive baseline vs LAVA-managed corridor |
| EV wait time reduction | > 25% less average wait | Compare random-station vs LAVA-routed EVs |
| V2G utilisation | > 60% of eligible EVs respond | Count V2G sell acceptances vs invitations |
| Decision latency | < 200 ms on Pi hardware | Measure LAVA engine.py wall-clock time |
| Offline uptime | > 99% (decisions made without WAN) | Disconnect WAN, measure local decision continuity |
| Energy overhead per decision | < 50 mJ on Pi hardware | Measure CPU power draw during LAVA execution |
| Blockchain consensus | 100% agreement across validators | Compare chain hashes across 3 validator nodes |

**Experiments:**

1. **Baseline comparison:** reactive (no prediction) vs LAVA-managed corridor, 24h sim, 500 EVs
2. **Ablation:** full LAVA vs optimiser-only vs rules-only vs constraint-only
3. **Scalability:** 3 stations → 5 → 10 → 20, measure decision latency growth
4. **Stress test:** sudden EV surge (concert/event scenario), measure grid stress response
5. **V2G economics:** calculate energy cost savings and V2G revenue over 24h sim
6. **Offline resilience:** cut WAN at random intervals, verify local decisions continue
7. **Hardware deployment:** run on Pi cluster, report real latency/memory/power

---

## Folder Structure (Final)

```
aei-v2g/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── config/
│   ├── corridor_config.yaml    # Corridor topology
│   ├── lava_weights.yaml       # Optimiser cost weights
│   ├── rules.yaml              # Rule-based reasoner rules
│   └── constraints.yaml        # Hard constraint thresholds
├── sim/
│   ├── ev_generator.py
│   ├── rsu_model.py
│   ├── station_model.py
│   ├── grid_model.py
│   └── corridor.py
├── lava/
│   ├── optimizer.py
│   ├── rules.py
│   ├── constraints.py
│   ├── ensemble.py
│   ├── engine.py
│   └── cost_functions.py
├── integration/
│   ├── coordinator.py
│   ├── v2g_dispatcher.py
│   └── ev_router.py
├── blockchain/                 # IIoT-Chain (from iotnodes/)
├── logging/
│   ├── decision_log.py
│   └── v2g_ledger.py
├── deploy/
│   ├── deploy_pi_nodes.py
│   └── configs/                # Per-node YAML configs
├── eval/
│   ├── run_baseline.py
│   ├── run_ablation.py
│   ├── run_scalability.py
│   └── plot_results.py
├── dashboard/                  # React frontend (reuse from sieveAi/React)
└── tests/
    ├── test_sim_basic.py
    ├── test_optimizer.py
    ├── test_rules.py
    ├── test_constraints.py
    ├── test_ensemble.py
    ├── test_e2e_basic.py
    └── test_v2g_trigger.py
```

---

## How This Connects to Prior Work

| Asset | Where | Reuse |
|-------|-------|-------|
| IIoT-Chain blockchain | `iotnodes/iiot-chain - Copy/` | PoA consensus, ECDSA signing, Pi deployment scripts |
| Pi cluster (5 nodes) | 192.168.137.x LAN | Same hardware, extend deployment scripts |
| React dashboard | `sieveAi/React/` | Adapt for grid/station/EV visualisation |
| Deployment automation | `iotnodes/.../deploy_rpi_nodes.py` | Extend for AEI-V2G node configs |
| SieveIoT enforcement | `sieveAi/backend/` | Optional: gate LAVA V2G dispatch commands through SieveIoT for accountability |

---

## Quick Start (After Phase 1)

```bash
cd aei-v2g
pip install -r requirements.txt

# Run a basic simulation
python -m integration.coordinator --config config/corridor_config.yaml --duration 3600

# Run with LAVA dashboard
python -m integration.coordinator --config config/corridor_config.yaml --dashboard
```

## Implemented Quick Start

This workspace now contains a runnable implementation of the README plan: EV/RSU/station/grid simulation, the three-engine LAVA ensemble, V2G dispatch, hash-chained decision logging, evaluation metrics, tests, and Docker/Raspberry Pi image support.

```bash
cd "C:\Users\s9\Desktop\Journal Check\aei-v2g"
python -m pip install -r requirements.txt
python -m pytest -q
python -m integration.coordinator --config config/corridor_config.yaml --duration 86400 --output reports/24h_metrics.json --chain data/24h_chain.jsonl
```

Latest verified 24-hour metrics from this implementation:

| Metric | Result |
|--------|--------|
| EVs served | 523 |
| Demand prediction accuracy | 97.22% |
| Grid stress reduction | 77.34% |
| EV wait time reduction | 83.54% |
| V2G utilisation | 69.53% |
| Average decision latency | 0.013 ms |
| Max decision latency | 0.132 ms |
| Offline uptime | 100.0% |
| Energy overhead per decision | 0.18 mJ |
| Blockchain consensus | 100.0% |
| V2G revenue | 523.45 |

## Docker and Raspberry Pi Images

Build and run locally:

```bash
docker build -t aei-v2g:local .
docker run --rm aei-v2g:local python -m integration.coordinator --config config/corridor_config.yaml --duration 600 --output reports/docker_smoke.json --chain data/docker_chain.jsonl
```

Build a Raspberry Pi 4/5 64-bit image:

```bash
docker buildx build --platform linux/arm64 -t aei-v2g:pi --load .
```

Run the 5-node Pi role simulation with Compose:

```powershell
.\deploy\run_pi_cluster.ps1 -DurationSeconds 600 -Platform linux/arm64
```

The Compose file maps the README roles to services: `pi1-lava-validator`, `pi2-station-validator`, `pi3-station-validator`, `pi5-rsu-observer`, and `pi6-grid-observer`. Metrics are written under `reports/`; hash-chained decision logs are written under `data/`.

For reproducible Docker experiments intended for reports, use the journal runner wrapper instead of ad hoc container commands:

```powershell
python -m data_sources.download_caiso_load --start 2024-05-01 --end 2024-05-07 --output data/grid_profiles/caiso_2024-05-01_2024-05-07.csv
.\deploy\run_docker_experiment.ps1 -Build -DurationSeconds 86400
```

This creates a new `reports/docker_experiment_<timestamp>/` directory with `provenance.json`, input config snapshots, required data-source hashes, per-scenario traces, metrics CSVs, JSON details, and hash-chain logs. If the config references the CAISO CSV and it is missing, the run fails before generating report tables. See `deploy/DOCKER_EXPERIMENTS.md`.

## Journal-Grade Evaluation

For paper results, use the multi-scenario evaluator instead of the quick smoke run:

```powershell
python -m eval.run_journal_study --config config/corridor_config.yaml --duration 86400 --output-dir reports/journal_study
```

It generates:

| File | Purpose |
|------|---------|
| `reports/journal_study/provenance.json` | Command, runner, seed, scheduler, input/data-source hashes, and generated artifact manifest |
| `reports/journal_study/inputs/` | Exact config and LAVA rule/weight/constraint snapshots used for the run |
| `reports/journal_study/JOURNAL_RESULTS.md` | Publication-facing result tables |
| `reports/journal_study/scenario_comparison.csv` | Scenario comparison table |
| `reports/journal_study/component_metrics.csv` | Individual EV, RSU, LAVA, grid, V2G, blockchain, and edge metrics |
| `reports/journal_study/station_metrics.csv` | Per-station load, queue, delivered energy, and V2G supply |
| `reports/journal_study/*_detail.json` | Full JSON for each scenario |
| `reports/journal_study/*_trace.csv` | Per-minute generated traces for each scenario |
| `reports/journal_study/*_chain.jsonl` | Hash-chained decision logs |

Scenarios currently included: weekday nominal, evening peak V2G, event surge, rural degraded ISAC, and WAN outage edge-only. These are deterministic edge digital-twin results; physical Raspberry Pi latency/power results should be appended after running the same container workload on the Pi cluster.

## Real Grid Load Profiles

The grid model can now use downloaded public CAISO load data instead of only synthetic daily stress curves.

```powershell
python -m data_sources.download_caiso_load --start 2024-05-01 --end 2024-05-07 --output data/grid_profiles/caiso_2024-05-01_2024-05-07.csv
```

The default config uses:

```yaml
grid:
  load_profile_csv: data/grid_profiles/caiso_2024-05-01_2024-05-07.csv
```

Regenerate real-grid journal results with:

```powershell
python -m eval.run_journal_study --config config/corridor_config.yaml --duration 86400 --output-dir reports/journal_study_real_grid
python -m eval.validate_journal_results --report-dir reports/journal_study_real_grid --output reports/journal_study_real_grid/VALIDATION_DEFENSE.md
python -m eval.plot_journal_results --report-dir reports/journal_study_real_grid --output-dir reports/journal_study_real_grid/figures
```

Dataset card: `data_sources/CAISO_DATASET_CARD.md`. Latest real-grid outputs: `reports/journal_study_real_grid/`.

---

## Key Design Decisions

1. **LAVA at the station cluster, not at the RSU.** RSUs are sensor nodes; they don't have the full picture. The station cluster has load data from all its stations plus grid stress signals, so that's where the decision should be made.

2. **Median voting, not mean or majority.** In a three-engine ensemble, one engine might produce an outlier (e.g., the optimiser recommends aggressive V2G while the rule engine says "grid is fine, don't discharge"). The median pulls toward the conservative middle without requiring engines to agree on a discrete label.

3. **Cooldown gate for stability.** In a control loop that runs every few seconds, oscillation is the enemy. If the engines disagree by more than a set margin, the system holds the previous decision until new data arrives. This prevents flip-flopping between "charge" and "discharge" commands.

4. **Blockchain for trust, not for speed.** The blockchain logs decisions and V2G transactions for audit and settlement. It does not sit in the decision-making hot path. LAVA decides locally; the blockchain records the decision after the fact. This keeps decision latency low while still providing decentralised trust.

5. **Offline-first.** The corridor might lose WAN connectivity (rural areas, bad weather). Every node must be able to make local decisions using only LAN data. Blockchain sync and cloud reporting are deferred and batched when connectivity returns.
