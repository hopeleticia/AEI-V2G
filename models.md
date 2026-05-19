# AEI-V2G System Models

**ISAC-Aided Proactive Vehicle-to-Grid Scheduling with Blockchain Incentive Layer**  
*Model decomposition, mathematical formulation, and implementation mapping*

---

## Overview

The AEI-V2G system decomposes into six distinct models. Each model has a defined set of inputs, outputs, and internal state. Together they form a closed-loop pipeline: the **Sensing Model** observes approaching EVs before they arrive; the **Environment Model** tracks grid and corridor dynamics; the **Battery Model** tracks per-EV energy state; the **Decision Model** (LAVA) uses all of the above to produce routing and dispatch decisions; the **Trust Model** records every decision immutably; and the **Evaluation Model** measures whether the system is doing its job.

---

## Dependency Flow

Sensing Model ──────────────────────────────┐
                                            ▼
Environment Model ──────────────► Decision Model ──► Trust Model
                                            │              │
Battery Model ──────────────────────────────┘              │
                                                           ▼
                                              Evaluation Model

```

---

## 1. Sensing Model

### Purpose

ISAC-equipped Roadside Units (RSUs) sense approaching EVs using reflected echoes from their own communication signals. The goal is to extract EV state *before* physical plug-in so that the Decision Model can act proactively. This is the primary novelty of the system — no prior V2G paper uses physical real-time sensing of approaching EVs.

### 1.1 RSU Coverage and Detection Condition

Each RSU $r$ is positioned at kilometre mark $x_r$ along the 50 km corridor with a sensing range $\rho = 7.5$ km. An EV $k$ at position $x_k$ is within sensing range of RSU $r$ if:

$$|x_k - x_r| \leq \rho$$

Four RSUs are deployed at $x_{r_1} = 4$, $x_{r_2} = 16$, $x_{r_3} = 31$, $x_{r_4} = 45$ km. An EV detected by multiple RSUs is deduplicated — the most recent observation is retained.

### 1.2 ETA Extraction

For an EV $k$ travelling at speed $v_k$ (km/h) currently at position $x_k$, the estimated time of arrival (ETA) at charging station $s_i$ located at kilometre mark $x_{s_i}$ is:

$$\hat{t}^{\text{arr}}_{k,i} = \frac{\max(0,\ x_{s_i} - x_k)}{v_k} \times 60 \quad \text{(minutes)}$$

Only forward stations ($x_{s_i} \geq x_k$) are included. ETAs are published with each RSU sense observation.

### 1.3 SoC Proxy Inference *(planned — Priority 6)*

The true State of Charge $\text{SoC}_k(t)$ is not directly observable before plug-in. The sensing model estimates a proxy $\hat{\text{SoC}}_k$ from ISAC channel features:

$$\hat{\text{SoC}}_k = f_\theta\bigl(\text{RSSI}_k,\ \Delta f_{\text{Doppler},k},\ d_k,\ \dot{v}_k\bigr)$$

where:
- $\text{RSSI}_k$ — received signal strength of the echo return
- $\Delta f_{\text{Doppler},k} = \frac{2 v_k}{\lambda_c}$ — Doppler shift proportional to radial velocity ($\lambda_c$ = carrier wavelength)
- $d_k = |x_k - x_r|$ — range to the sensing RSU
- $\dot{v}_k$ — vehicle deceleration rate (inferred from successive range measurements)

$f_\theta$ will initially be a ridge regression model trained on synthetic $(\text{features}, \text{SoC}_{\text{true}})$ pairs. Accuracy is reported as Mean Absolute Error at plug-in:

$$\text{MAE}_{\text{SoC}} = \frac{1}{K}\sum_{k=1}^{K} \bigl|\hat{\text{SoC}}_k - \text{SoC}_k(t_{\text{plug-in}})\bigr|$$

### 1.4 Published Feature Vector

Each RSU observation for EV $k$ produces:

$$\mathbf{z}_k = \bigl\{\text{ev\_id},\ x_k,\ v_k,\ \text{battery\_pct}_k,\ d_k,\ \hat{t}^{\text{arr}}_{k,i}\ \forall i,\ \hat{\text{SoC}}_k\bigr\}$$

Published on MQTT topic `aei/rsu/sense` once per tick per EV in range.

### 1.5 Implementation

| Component | File | Status |
|---|---|---|
| RSU detection + ETA | `sim/rsu_model.py` | Built |
| SoC proxy inference | `sensing/soc_proxy.py` | Not yet built |

---

## 2. Environment Model

### Purpose

The Environment Model captures the external conditions that the Decision Model must react to: the state of the electricity grid and the flow of EVs through the corridor. It is not controlled by the system — it is observed.

### 2.1 Grid Stress

Grid stress $\sigma(t) \in [0, 1]$ at minute $t$ is a composite measure of supply-demand imbalance:

$$\sigma(t) = \text{clip}\Bigl(\sigma_{\text{base}} + \sigma_{\text{wave}}(t) + \sigma_{\text{profile}}(t) + \sigma_{\text{peak}}(t) + \sigma_{\text{event}}(t) + \sigma_{\text{load}}(t) - \sigma_{\text{relief}}(t),\ 0,\ 1\Bigr)$$

where:

$$\sigma_{\text{wave}}(t) = 0.04 \cdot \sin\!\left(\frac{h(t) - 6}{24} \cdot 2\pi\right), \quad h(t) = \left\lfloor\frac{t}{60}\right\rfloor \bmod 24$$

$$\sigma_{\text{profile}}(t) = 0.28 \cdot \tilde{P}_{\text{CAISO}}(t), \quad \tilde{P}_{\text{CAISO}} \in [0,1] \text{ normalised}$$

$$\sigma_{\text{peak}}(t) = \begin{cases} 0.18 & h(t) \in \{7, 8, 17, 18, 19\} \\ 0 & \text{otherwise} \end{cases}$$

$$\sigma_{\text{event}}(t) = \begin{cases} 0.22 & h(t) = 18 \\ 0 & \text{otherwise} \end{cases}$$

$$\sigma_{\text{load}}(t) = \min\!\left(0.32,\ \frac{P_{\text{station}}(t)}{1600}\right)$$

$$\sigma_{\text{relief}}(t) = \min\!\left(0.20,\ \frac{P_{\text{V2G}}(t)}{800}\right)$$

The grid profile $\tilde{P}_{\text{CAISO}}(t)$ is the real CAISO demand data for 2024-05-01 to 2024-05-07 at 5-minute resolution, accessed cyclically.

### 2.2 Time-of-Use Pricing

Real-time electricity tariff and V2G buy price are functions of grid stress:

$$\lambda(t) = 0.24 + 0.20 \cdot \sigma(t) \quad \text{(\$/kWh)}$$

$$\lambda_{\text{V2G}}(t) = \lambda_{\text{base}} + 0.22 \cdot \sigma(t), \quad \lambda_{\text{base}} = 0.42 \text{ \$/kWh}$$

Grid frequency (used in V2G safety constraints):

$$f(t) = 50.0 - \max\!\bigl(0,\ \sigma(t) - 0.75\bigr) \times 0.35 \quad \text{(Hz)}$$

### 2.3 EV Arrival Process

EVs enter the corridor at position $x = 0$ following a Poisson process with arrival rate $\lambda_{\text{arr}} = 28$ EVs/hour. The number of new EVs in a tick of duration $\Delta t$ minutes:

$$N(\Delta t) \sim \text{Poisson}\!\left(\frac{\lambda_{\text{arr}} \cdot \Delta t}{60}\right)$$

Each EV is initialised with:
- Speed: $v_k \sim \mathcal{U}(70, 105)$ km/h
- Initial battery: $\text{SoC}_k(0) \sim \mathcal{N}(46, 18^2)$ %, clipped to $[8, 92]$
- Charge request: true if $\text{SoC}_k(0) < 62\%$ or with probability 0.18

### 2.4 Published State

Grid state is published on `aei/grid/state` every tick:

$$\mathbf{g}(t) = \bigl\{\sigma(t),\ \lambda(t),\ \lambda_{\text{V2G}}(t),\ f(t)\bigr\}$$

### 2.5 Implementation

| Component | File | Status |
|---|---|---|
| Grid stress + TOU | `sim/grid_model.py` | Built |
| CAISO profile loader | `sim/load_profile.py` | Built |
| EV arrival generator | `sim/ev_generator.py` | Built |
| Corridor topology | `sim/corridor.py` | Built |

---

## 3. Battery / Degradation Model

### Purpose

Tracks the energy state of each EV during its charging session. Provides the SoC trajectory needed to compute the reward function and to enforce the safety constraint that no EV battery is drained below 20%.

### 3.1 SoC Dynamics

Let $C_k$ (kWh) denote the usable capacity of EV $k$'s battery. During a charging interval of duration $\Delta t$ hours at power $P_k^{\text{charge}}$ (kW):

$$\text{SoC}_k(t + \Delta t) = \text{SoC}_k(t) + \frac{P_k^{\text{charge}} \cdot \Delta t}{C_k} \cdot \eta_{\text{charge}}$$

During a V2G discharge interval at power $P_k^{\text{V2G}}$ (kW):

$$\text{SoC}_k(t + \Delta t) = \text{SoC}_k(t) - \frac{P_k^{\text{V2G}} \cdot \Delta t}{C_k \cdot \eta_{\text{discharge}}}$$

The current simplified model uses $\eta_{\text{charge}} \approx 1$ and charges at 55 kW per slot until $\text{required\_kWh}_k = 0$.

### 3.2 Safety Constraint

A hard constraint prevents any scheduling decision from draining a battery below the minimum threshold:

$$\text{SoC}_k(t) \geq \text{SoC}^{\min} = 20\% \quad \forall k, t$$

This constraint is enforced by both the LAVA ConstraintEnforcer and the DRL safety layer in `scheduling/drl_scheduler.py`.

### 3.3 State of Health

Battery capacity degrades over charge-discharge cycles. SoH $\in [0, 1]$ is a capacity fade factor:

$$C_k^{\text{eff}}(t) = \text{SoH}_k \cdot C_k^{\text{nominal}}$$

A fresh battery has $\text{SoH}_k = 1.0$; a degraded battery might have $\text{SoH}_k = 0.85$, meaning it can only hold 85% of its original capacity.

### 3.4 Battery Degradation Cost

The weighted Ampere-hour throughput (wAh) model estimates degradation cost per charging event. For EV $k$ over a session with $M$ charge/discharge intervals:

$$C_{\text{deg},k} = c_{\text{rate}} \cdot \sum_{m=1}^{M} I_{k,m} \cdot |\Delta\text{SoC}_{k,m}|$$

where $I_{k,m}$ is the current magnitude (proportional to power), $|\Delta\text{SoC}_{k,m}|$ is the SoC change per interval, and $c_{\text{rate}}$ is a battery-chemistry-specific degradation coefficient. The total degradation cost across all EVs at time slot $t$:

$$C_{\text{deg}}(t) = \sum_{k \in \mathcal{K}(t)} C_{\text{deg},k}(t)$$

### 3.5 SoC Satisfaction

An EV $k$ achieves SoC satisfaction if it reaches its requested charge level by its departure time:

$$\text{sat}_k = \mathbf{1}\!\left[\text{SoC}_k(T^{\text{dep}}_k) \geq \text{SoC}^{\text{req}}_k\right]$$

### 3.6 Per-EV Feature Set

$$\mathbf{b}_k(t) = \bigl\{\text{SoC}_k(t),\ \text{SoH}_k,\ \text{SoC}^{\text{req}}_k,\ T^{\text{dep}}_k,\ C_k\bigr\}$$

### 3.7 Implementation

| Component | File | Status |
|---|---|---|
| EV entity (battery_pct field) | `sim/entities.py` | Partially built |
| Charging dynamics | `sim/station_model.py` | Built (simplified) |
| Full SoC trajectory tracking | — | **Not yet built (Priority 2)** |
| wAh degradation cost | — | **Not yet built** |

---

## 4. Decision Model — LAVA

### Purpose

LAVA (the scheduling engine on pi1) makes two types of decisions every tick:

1. **Routing** — which charging station to assign each approaching EV that is currently in RSU range.
2. **V2G dispatch** — how much aggregate power (kW) to draw from plugged-in EVs back to the grid.

LAVA is a three-engine ensemble with median voting. It uses a fixed weighted cost function, an expert rules engine, and a constraints enforcer.

### 4.1 Three-Engine Ensemble

At each decision step, three engines independently produce a candidate:

$$\mathcal{C} = \bigl\{c_{\text{opt}},\ c_{\text{rules}},\ c_{\text{constraints}}\bigr\}$$

Each candidate $c$ carries: `action`, `station_id`, `value_kw`, `confidence` $\in [0,1]$, `engine`, `reason`.

The ensemble aggregates these via **median voting** (described in §4.4).

### 4.2 Engine 1 — Global Optimizer

For each candidate station $s_i$, a weighted cost is computed:

$$J(s_i) = w_1 \cdot \sigma(t) \cdot u_i + w_2 \cdot \frac{\hat{t}^{\text{arr}}_{k,i} + q_i}{60} + w_3 \cdot |u_i - \bar{u}| + w_4 \cdot p_i$$

where:
- $\sigma(t)$ — current grid stress
- $u_i = P_i / P_i^{\max}$ — station utilisation
- $\hat{t}^{\text{arr}}_{k,i}$ — ETA of EV $k$ to station $s_i$ (minutes)
- $q_i$ — estimated queue wait at $s_i$ (minutes)
- $\bar{u} = \frac{1}{|S|}\sum_i u_i$ — mean utilisation across all stations
- $p_i = \lambda_{\text{base},i} + \lambda(t)$ — combined energy price at station $s_i$

Weights (from `config/lava_weights.yaml`):

| Weight | Value | Penalises |
|---|---|---|
| $w_1$ (grid stress) | 0.32 | Routing to high-stress, high-utilisation stations |
| $w_2$ (EV wait time) | 0.28 | Long travel time + queue wait |
| $w_3$ (station imbalance) | 0.22 | Over-concentrating EVs at one station |
| $w_4$ (energy cost) | 0.18 | Higher-price stations |

The routing decision from the optimizer:

$$s^*_{\text{opt}} = \arg\min_{i \in S} J(s_i)$$

For V2G dispatch, the optimizer outputs a stress-proportional power level:

$$P^{\text{V2G}}_{\text{opt}}(t) = \max\!\bigl(0,\ (\sigma(t) - 0.72) \times 520\bigr) \quad \text{(kW)}$$

The dispatch threshold of 0.72 creates a dead zone below the critical stress level, preventing unnecessary battery cycling.

### 4.3 Engine 2 — Rule Reasoner

The rules engine applies priority-ordered expert heuristics:

**Routing rules** (evaluated in order):

| Priority | Condition | Action |
|---|---|---|
| 1 | $\text{SoC}_k < 25\%$ (low battery) | Route to nearest station |
| 2 | $\exists s_i : \text{available\_slots}_i > 0$ | Route to lowest-price open station with shortest queue |
| 3 | All stations full | Route to station with shortest queue |

**V2G dispatch rule:**

$$P^{\text{V2G}}_{\text{rules}}(t) = \begin{cases} n_{\text{eligible}}(t) \times 18 \text{ kW} & \sigma(t) \geq 0.8 \\ 0 & \text{otherwise} \end{cases}$$

where $n_{\text{eligible}}(t) = |\{k : \text{SoC}_k(t) \geq 55\%\}|$ is the count of EVs with sufficient charge to safely discharge.

### 4.4 Engine 3 — Constraint Enforcer

Enforces hard system limits and overrides any candidate that would violate them:

| Constraint | Parameter | Value |
|---|---|---|
| Minimum SoC after V2G | $\text{SoC}^{\min}$ | 20% |
| Maximum station utilisation | $u^{\max}$ | 0.98 |
| Maximum grid frequency deviation | $\Delta f^{\max}$ | 0.25 Hz |
| Minimum decision confidence | $\gamma^{\min}$ | 0.35 |
| Maximum engine divergence | $\delta^{\max}$ | 0.55 |

The constraint enforcer also avoids routing to stations where utilisation would exceed $u^{\max}$ unless no alternative exists.

### 4.5 Median Ensemble and Cooldown Gate

**Routing:** Stations are voted on by confidence-weighted ballot across the three candidates. The station with the highest aggregate confidence weight wins:

$$s^* = \arg\max_{s_i} \sum_{c \in \mathcal{C}} \text{conf}(c) \cdot \mathbf{1}[c.\text{station\_id} = s_i]$$

Disagreement is measured as:

$$\delta_{\text{route}} = 1 - \frac{\text{votes}(s^*)}{\sum_i \text{votes}(s_i)}$$

**V2G dispatch:** The ensemble applies the median of the three power values:

$$P^{\text{V2G}}(t) = \text{median}\bigl(P^{\text{V2G}}_{\text{opt}},\ P^{\text{V2G}}_{\text{rules}},\ P^{\text{V2G}}_{\text{constraints}}\bigr)$$

Divergence is normalised:

$$\delta_{\text{V2G}} = \frac{\max(P) - \min(P)}{\max(1, \max(P))}$$

**Cooldown gate:** If the median confidence $\bar{\gamma} < \gamma^{\min}$ or divergence $\delta > \delta^{\max}$, the previous accepted decision is retained (no change). This prevents oscillation in the control loop.

$$\text{decision}(t) = \begin{cases} \text{new decision} & \bar{\gamma} \geq \gamma^{\min} \text{ and } \delta \leq \delta^{\max} \\ \text{decision}(t-1) & \text{otherwise (cooldown)} \end{cases}$$

### 4.6 Pre-Arrival Slot Reservation *(planned)*

The novel scheduling action enabled by ISAC sensing: commit a charging slot to an approaching EV *before it arrives*, at time $\hat{t}^{\text{arr}}_{k,i} - \Delta$ minutes ahead of its predicted arrival. This reduces scheduling lag to near zero. No existing V2G scheduler implements this action.

### 4.7 Decision Latency

Because LAVA is a weighted sum and rule evaluation (not a neural network), decision latency is sub-millisecond:

$$\bar{L}_{\text{LAVA}} = 0.397 \text{ ms} \quad \text{(measured on Raspberry Pi 4, 20-minute cluster run)}$$

### 4.8 Implementation

| Component | File | Status |
|---|---|---|
| LAVA engine orchestrator | `lava/engine.py` | Built |
| Global optimizer | `lava/optimizer.py` | Built |
| Rule reasoner | `lava/rules.py` | Built |
| Constraint enforcer | `lava/constraints.py` | Built |
| Median ensemble + cooldown | `lava/ensemble.py` | Built |
| Pluggable scheduler interface | `scheduling/base_scheduler.py` | Built |
| LAVA adapter (base interface) | `scheduling/lava_scheduler.py` | Built |
| Pre-arrival slot reservation | — | **Not yet built (Priority 1 extension)** |

---

## 5. Trust Model

### Purpose

Every decision made by every node is recorded in a tamper-evident audit log and anchored to a private Ethereum blockchain. The Trust Model has two layers: an **audit layer** (already built) and an **incentive layer** (planned).

### 5.1 Local Hash-Chain (Audit Layer)

Each node maintains an append-only JSONL log. Records are chained by SHA-256 hash:

$$h_n = \text{SHA-256}\!\left(h_{n-1} \,\|\, \text{record}_n\right)$$

where $\|$ denotes concatenation and $h_0 = \text{SHA-256}(\text{""})$. Any tampering with a historical record invalidates all subsequent hashes.

Cross-node integrity is verified periodically: each node broadcasts its current chain tail on `aei/chain/sync`. A divergence in the hash tree signals a consistency violation.

### 5.2 On-Chain Anchoring

The hash of each local record is submitted as calldata in a 0-ETH transaction to the private Hardhat chain:

$$\text{tx}_n : \text{from} = \text{account}(\text{node\_id}),\ \text{to} = \text{LOG\_SINK},\ \text{data} = (\text{event\_type} \,\|\, h_n)$$

This creates an externally verifiable, gas-efficient audit trail. Chain parameters:

- RPC endpoint: `https://myprivatechain.onrender.com`
- Chain ID: `0x539` (Hardhat)
- Log sink: `0x90F79bf6EB2c4f870365E785982E1f101E93b906`
- Final block height after 20-minute run: `0x98` (152 blocks)

### 5.3 Credit-Point Incentive Ledger *(planned — Priority 7)*

EVs are incentivised to participate in V2G discharge during grid stress events through a credit-point reward:

$$\text{credits}_k \mathrel{+}= \left\lfloor \frac{E^{\text{V2G}}_k}{r_{\text{credit}}} \right\rfloor \quad \text{if } \sigma(t) \geq \sigma_{\text{critical}}$$

where $E^{\text{V2G}}_k$ (kWh) is the energy discharged by EV $k$ in a session and $r_{\text{credit}} = 0.5$ kWh/credit (1 credit per 0.5 kWh discharged during peak).

Credits are redeemable against future charging costs:

$$\text{discount}_k = \text{credits}_k \times r_{\text{redemption}}$$

The ledger is implemented as a Solidity smart contract (`contracts/CreditLedger.sol`) with three public functions:

| Function | Signature | Description |
|---|---|---|
| Award | `award_credits(ev_id, kwh)` | Mint credits after V2G discharge |
| Redeem | `redeem_credits(ev_id, amount)` | Deduct credits for charging discount |
| Query | `get_balance(ev_id)` | Read current credit balance |

The V2G settlement record on-chain stores:
$$\text{settlement}_k = \{\text{ev\_id},\ \text{station\_id},\ E^{\text{V2G}}_k,\ \text{credits\_awarded},\ t\}$$

EVs earn both monetary compensation ($\lambda_{\text{V2G}}(t)$ per kWh) and credit points — the two incentive streams are additive.

### 5.4 Implementation

| Component | File | Status |
|---|---|---|
| SHA-256 hash chaining | `logging_layer/decision_log.py` | Built |
| Ethereum anchoring | `logging_layer/chain_client.py` | Built |
| CreditLedger smart contract | `contracts/CreditLedger.sol` | **Not yet built** |
| `award_credits` / `redeem_credits` | `logging_layer/chain_client.py` | **Not yet built** |

---

## 6. Evaluation Model

The evaluation model defines the eight metrics used to compare schedulers and validate the system's claims. Each metric is chosen to answer a specific research question: does the scheduler smooth grid demand, reduce cost, respect drivers, respond quickly, protect batteries, demonstrate that sensing actually helps, and accurately infer pre-arrival state? No single metric is sufficient on its own — together they form a complete picture of grid-side performance, user-side acceptability, safety, and novelty.

---

### 6.1 Peak-to-Average Ratio (PAR)

$$\text{PAR} = \frac{P_{\text{peak}}}{\bar{P}} = \frac{\max_t P_{\text{grid}}(t)}{\frac{1}{T}\sum_{t=1}^{T} P_{\text{grid}}(t)}$$

**What it measures.** PAR compares the single worst-case demand spike during an episode to the average demand over the same period. A value of 1.0 would mean perfectly flat load — every time-step draws the same power, which is physically ideal but practically unachievable. A value of 3.0 means the peak drew three times the average, which stresses transformer capacity and incurs demand charges.

**Why it is the right metric here.** The central promise of V2G is that EVs do not just consume power passively — they can absorb or return power in a coordinated way to flatten the grid's demand curve. PAR directly measures whether that coordination is working. If PAR is high, the scheduler is either failing to spread charging across time, failing to call V2G discharge during peaks, or both. PAR is also the metric grid operators care about most: high-PAR events are what cause transformer overloads, emergency curtailment requests, and infrastructure replacement costs. Using the CAISO 2024-05-01 to 2024-05-07 real demand profile as the grid stress signal makes the PAR values directly comparable to real-world California grid conditions.

**What the values mean in practice.**

| PAR range | Interpretation |
|---|---|
| < 1.3 | Excellent — scheduler is actively flattening peaks |
| 1.3–1.8 | Good — meaningful improvement over uncontrolled charging |
| 1.8–2.5 | Marginal — some smoothing but notable peaks remain |
| > 2.5 | Poor — close to uncontrolled charging behaviour |

**Connection to the paper's claims.** The ablation table compares B1 (reactive, no sensing), B3 (LAVA + ISAC), and Ours (DRQN + ISAC). A meaningful PAR reduction from B1 to B3 validates that even rule-based scheduling helps; a further reduction from B3 to Ours validates that learning adds additional smoothing beyond rules. The benchmark from the literature (Paper 3, Transfer DRL V2G) achieves 97.37% load variance reduction, which sets the upper target.

**Caveat.** PAR is sensitive to episode length and time-step resolution — comparing PAR values across systems with different simulation clocks is misleading. All three ablation conditions must use identical episode lengths and tick intervals ($\Delta t$) for fair comparison.

---

### 6.2 Total Energy Cost (TEC)

$$\text{TEC} = \sum_{k=1}^{K} \sum_{t=1}^{T} P_k(t) \cdot \lambda(t) \cdot \Delta t \quad \text{(\$)}$$

where $P_k(t) > 0$ is charging power (cost to the EV owner) and $P_k(t) < 0$ is V2G discharge power (revenue to the EV owner), so V2G participation reduces TEC.

**What it measures.** TEC is the net monetary outcome for EV owners across an episode. It accumulates the cost of every charging kilowatt-hour purchased at the time-of-use tariff $\lambda(t)$, minus the revenue earned from every kilowatt-hour returned to the grid during V2G discharge. A negative TEC would mean the fleet as a whole earned more from V2G than it spent on charging — a theoretical maximum that is rarely achieved but useful as a reference point.

**Why it is the right metric here.** EV adoption depends on economic appeal. If a smart V2G system raises charging costs relative to uncontrolled overnight charging, drivers will opt out of coordination protocols regardless of grid benefits. TEC captures whether the scheduler is shifting charging towards cheap off-peak tariff windows and whether V2G dispatch timing is aligned with high-value grid export periods. It is the primary metric for driver-facing acceptability and directly answers the question: "Does participating in this system save me money?"

**What the values mean in practice.** TEC is most informative as a relative comparison. The baseline is uncontrolled charging (charge immediately on arrival at maximum rate). A well-designed scheduler should reduce TEC by 15–30% through tariff-aware scheduling alone, with an additional reduction from V2G revenue. The V2G price $\lambda_{\text{V2G}}(t)$ being higher than the off-peak tariff is the economic condition that makes V2G worth participating in.

**Connection to the paper's claims.** The DRQN reward function includes $-\beta \cdot \text{TEC}(t)$ as a training signal, meaning the DRL scheduler is directly optimised to reduce cost. LAVA, being rule-based, reduces TEC indirectly by shifting load to low-tariff slots via its cost function $J(s_i)$. Comparing TEC across B1, B3, and Ours shows whether the learned policy extracts additional cost savings beyond what the rules can achieve.

**Caveat.** TEC depends heavily on the tariff profile used. The CAISO-derived tariff schedule has a specific peak-hour structure; results may not generalise to flat-rate tariff regions. The paper should note the tariff assumptions explicitly when reporting TEC figures.

---

### 6.3 SoC Satisfaction Ratio

$$\rho_{\text{sat}} = \frac{\left|\left\{k : \text{SoC}_k\!\left(T^{\text{dep}}_k\right) \geq \text{SoC}^{\text{req}}_k\right\}\right|}{K_{\text{total}}} \times 100\%$$

**What it measures.** This ratio counts the fraction of EVs that leave the charging station with at least as much charge as the driver requested. If a driver declares they need 80% SoC by 8 am and the system delivers 79%, that EV counts as unsatisfied. The metric is binary per EV (satisfied or not) and averaged across the fleet.

**Why it is the right metric here.** V2G scheduling involves deliberate controlled discharge of EV batteries back to the grid. This creates a direct conflict: the more aggressively the scheduler uses an EV for V2G, the more it risks depleting the battery below the driver's requested level. Without tracking satisfaction, an aggressive DRL policy could learn to maximise grid-side metrics (PAR, TEC) by cannibalising driver SoC, which would make the system unacceptable in deployment. The 90% threshold used as a deployment bar is not arbitrary — surveys of EV driver behaviour consistently show that range anxiety is the primary adoption barrier, and a system that fails to charge 1 in 10 cars would lose driver trust rapidly.

**What the values mean in practice.**

| $\rho_{\text{sat}}$ | Interpretation |
|---|---|
| ≥ 95% | Excellent — drivers can rely on the system |
| 90–95% | Acceptable — meets deployment threshold |
| 80–90% | Marginal — some drivers will be affected noticeably |
| < 80% | Unacceptable — system is prioritising grid over users |

**Connection to the paper's claims.** The SoC safety layer (veto any V2G action that would push a battery below 20%) is the hard engineering constraint that prevents $\rho_{\text{sat}}$ from collapsing. The satisfaction ratio validates that this constraint is effective in practice. It also validates that the 20% floor is not so conservative that it blocks useful V2G dispatch — a system with 100% satisfaction and zero V2G revenue is not useful either.

**Caveat.** $\rho_{\text{sat}}$ treats all EVs equally regardless of battery size. An EV that arrives at 22% SoC and needs 90% by departure has a much harder constraint to satisfy than one that arrives at 60% and needs 80%. The metric does not capture this heterogeneity. A more nuanced version would weight by constraint tightness, but the binary version is standard in V2G literature and sufficient for a first paper.

---

### 6.4 Scheduling Lag

$$L_k = T^{\text{dispatch}}_k - T^{\text{arrive}}_k \quad \text{(seconds)}$$

**What it measures.** Scheduling lag is the delay between the moment an EV physically arrives at a charging station and the moment the system issues its first charging or V2G dispatch decision for that EV. In a reactive system, this delay includes: plug-in detection, protocol handshake, SoC measurement, scheduler computation, and response transmission. In a proactive ISAC-aided system, the scheduling decision can be computed before the EV arrives, reducing the lag to near zero.

**Why it is the right metric here.** Scheduling lag is the operationally observable signature of ISAC's value. The entire point of having RSUs sense approaching EVs via radar is to eliminate or drastically reduce this dead time. During the lag window, either (a) the EV sits idle at the station wasting connection time, or (b) the charger defaults to maximum-rate uncontrolled charging, which is exactly the PAR-spiking behaviour the scheduler is supposed to prevent. If lag is high, ISAC's pre-arrival information is not being used effectively. If lag is near zero across the fleet, it validates that the sensing pipeline (RSU → MQTT → scheduler → dispatch) is working end-to-end in real time.

**What the values mean in practice.**

| System | Scheduling Lag |
|---|---|
| Reactive V2G (no sensing) | 30–90 seconds |
| ISAC-aided (LAVA or DRQN) | Near zero (pre-arrival reservation) |

For the 5-node Raspberry Pi cluster, "near zero" in practice means the round-trip latency of the MQTT messages plus scheduler computation time, which should be under 200 ms even on constrained hardware.

**Connection to the paper's claims.** Scheduling lag is the quantitative bridge between the ISAC sensing model (Section 2) and the scheduling model (Section 4). A statistically significant reduction in lag from B1 (no sensing) to B3 and Ours (ISAC-aided) validates that the RSU radar sensing is translating into real scheduling acceleration. This is important because sensing adds system complexity and hardware cost — the lag reduction must justify that investment.

**Caveat.** On a simulated cluster, lag is partially artificial. The simulation must faithfully model the MQTT round-trip time and not shortcut it by allowing instant information access. If the simulator allows the scheduler to know EV state before the sensing message arrives, the lag metric will be artificially low and the sensing advantage overstated.

---

### 6.5 Battery Degradation Cost

$$C_{\text{deg}}^{\text{total}} = \sum_{k=1}^{K} c_{\text{rate}} \sum_{m} I_{k,m} \cdot |\Delta\text{SoC}_{k,m}|$$

where $I_{k,m}$ is the C-rate (charge/discharge rate relative to battery capacity) during interval $m$, $|\Delta\text{SoC}_{k,m}|$ is the magnitude of the SoC change during that interval, and $c_{\text{rate}}$ is a cost coefficient mapping degradation to monetary units (\$/% SoC-cycle).

**What it measures.** Every charge and discharge cycle degrades a lithium-ion battery. The degradation cost model estimates the economic damage done to EV batteries by the scheduling decisions. High C-rates (fast charging or fast V2G discharge) cause disproportionately more degradation than slow rates. The metric accumulates this damage across all EVs and all intervals in an episode, converting it to a dollar figure via $c_{\text{rate}}$.

**Why it is the right metric here.** V2G discharge uses the EV battery as a grid asset, which accelerates degradation. This is the main reason EV drivers are reluctant to participate in V2G programs — they worry about hidden battery replacement costs. Without tracking degradation cost, an optimizer could learn to extract maximum V2G revenue by cycling batteries aggressively, which would look good on PAR and TEC metrics while silently destroying battery longevity. The target — degradation increase below 15% over the uncontrolled charging baseline — sets the bar: the scheduler must not harm batteries significantly more than the driver would experience by simply charging on arrival.

**What the values mean in practice.** In absolute terms, battery degradation per session is small (fractions of a percent of battery capacity). The metric becomes meaningful as a cumulative figure across thousands of sessions over the EV's lifetime, or as a relative comparison: a scheduler that causes 14% more degradation than baseline is acceptable; one that causes 30% more is not.

**Connection to the paper's claims.** Degradation cost appears in the DRQN reward function as $-\gamma \cdot C_{\text{deg}}(t)$ with weight $\gamma = 0.1$. This intentionally gives degradation less weight than PAR ($\alpha = 0.4$) and TEC ($\beta = 0.3$) — the system prioritises grid and cost performance but does not completely ignore battery health. Reporting the degradation cost in the evaluation table shows whether that weighting choice produced acceptable outcomes.

**Caveat.** The degradation model is a simplified linear approximation. Real lithium-ion degradation is nonlinear, depends on temperature, SoC operating range, and calendar aging, none of which are modelled here. The metric is therefore best interpreted as a relative indicator (scheduler A causes more degradation than scheduler B) rather than an absolute prediction of battery lifetime.

---

### 6.6 Sensing Gain (ΔJ)

$$\Delta J = \bar{J}_{\text{ISAC}} - \bar{J}_{\text{no-ISAC}}$$

where $\bar{J}$ is the mean cumulative episode reward averaged across evaluation episodes.

**What it measures.** Sensing gain isolates the causal contribution of ISAC radar sensing to scheduling performance. It is computed by running the same scheduling algorithm twice — once with sensing-derived features (ETA, pre-arrival SoC proxy) in the state vector, and once without — and measuring the difference in cumulative reward. If $\Delta J > 0$, sensing inputs genuinely improved decisions. If $\Delta J \approx 0$, the scheduler was ignoring the sensing information or it provided no advantage over reactive scheduling.

**Why it is the right metric here.** The novelty of this system is the ISAC integration. Every other component — V2G scheduling, DRL, even the edge cluster — has been done before. The claim that sensing improves scheduling has not been directly quantified in prior work. Sensing gain is the metric that makes this claim falsifiable. Without it, the paper would argue "ISAC helps" based on system design alone rather than measured outcomes. A positive, statistically significant $\Delta J$ is the empirical foundation of the paper's contribution.

**What the values mean in practice.** The magnitude of $\Delta J$ depends on the reward scale, which is system-specific. What matters is whether it is significantly greater than zero (which requires enough evaluation episodes to establish statistical confidence) and whether the ratio $\Delta J / \bar{J}_{\text{no-ISAC}}$ represents a meaningful percentage improvement (target: ≥ 5–10% relative gain to be worth the sensing hardware cost).

**Connection to the paper's claims.** The ablation table has three conditions for exactly this reason:

| Condition | Sensing | Learning | Purpose |
|---|---|---|---|
| B1 — Reactive LAVA | No | No | No-sensing, no-learning floor |
| B3 — LAVA + ISAC | Yes | No | Isolates sensing gain (deterministic baseline) |
| Ours — DRQN + ISAC | Yes | Yes | Full system |

$\Delta J$ = B3 minus B1 gives the sensing gain under deterministic (LAVA) scheduling. The same comparison for Ours minus a hypothetical DRQN-no-ISAC condition gives the sensing gain under learned scheduling. Both should be positive for the paper's claims to hold.

**Caveat.** $\Delta J$ is measured in reward units, not in any directly interpretable unit like dollars or MW. Its meaning is only as good as the reward function design. If the reward function poorly represents the real objectives, a high $\Delta J$ could reflect gaming of the reward rather than genuine improvement. This is why $\Delta J$ must be corroborated by improvements in the primary metrics (PAR, TEC, $\rho_{\text{sat}}$).

---

### 6.7 SoC Proxy Estimation Error

$$\text{MAE}_{\text{SoC}} = \frac{1}{K}\sum_{k=1}^{K}\bigl|\hat{\text{SoC}}_k - \text{SoC}_k(t_{\text{plug-in}})\bigr|$$

where $\hat{\text{SoC}}_k$ is the SoC inferred by the ISAC sensing model before the EV arrives and $\text{SoC}_k(t_{\text{plug-in}})$ is the ground-truth SoC measured at the moment of physical plug-in.

**What it measures.** This metric validates the quality of the pre-arrival SoC estimate that the sensing pipeline provides. The ISAC system uses radar-derived range, Doppler speed, and the battery drainage model to infer an EV's state of charge before it connects. MAE$_{\text{SoC}}$ tells us how close those estimates are to the truth: an MAE of 2% means the system is typically within 2 percentage points of the real SoC, while an MAE of 15% would mean the estimates are too noisy to be useful for scheduling.

**Why it is the right metric here.** The entire scheduling pre-computation advantage rests on the quality of the pre-arrival state estimate. If the SoC proxy is wildly inaccurate, pre-computed schedules will be immediately invalidated on plug-in, eliminating the lag advantage. More importantly, an inaccurate SoC estimate in the V2G dispatch decision could trigger the safety constraint incorrectly — either blocking a safe V2G discharge because the system overestimates battery fullness needs, or allowing a discharge that drops the real SoC below 20% because the system underestimates how low the battery already is. MAE$_{\text{SoC}}$ validates whether the sensing pipeline is accurate enough to be trusted for these decisions.

**Why it is novel.** No prior V2G paper reports a metric for pre-plug-in SoC estimation accuracy because no prior system attempts this inference. This is one of the two genuinely novel empirical contributions of the paper (the other being $\Delta J$). Reporting MAE$_{\text{SoC}}$ establishes a benchmark for future ISAC-V2G research.

**What the values mean in practice.** Battery packs operate over a range of roughly 20–100% usable SoC (80 percentage points). As a rough guide:

| MAE$_{\text{SoC}}$ | Interpretation |
|---|---|
| < 3% | Excellent — estimate is actionable without significant correction |
| 3–8% | Acceptable — small safety margin absorbs the error |
| 8–15% | Marginal — scheduling pre-computation advantage is reduced |
| > 15% | Poor — estimates are not reliable enough for scheduling decisions |

**Connection to the paper's claims.** Low MAE$_{\text{SoC}}$ is a prerequisite for the sensing gain claim to be credible. If the proxy is inaccurate, reviewers will question whether $\Delta J > 0$ comes from genuinely useful sensing or from the system getting lucky in simulation. A low MAE validates the sensing pipeline independently, making the rest of the evaluation results more convincing.

**Caveat.** This metric is currently blocked by the unbuilt `sensing/soc_proxy.py` component (Priority 6 in the build plan). The ground-truth comparison also requires full SoC trajectory tracking in `sim/entities.py` (Priority 2). Until both are built, MAE$_{\text{SoC}}$ can only be estimated analytically, not measured empirically.

---

### 6.8 Reward Function (Internal — DRQN only)

$$r(t) = -\alpha \cdot \Delta\text{PAR}(t) - \beta \cdot \text{TEC}(t) - \gamma \cdot C_{\text{deg}}(t) + \delta \cdot \rho_{\text{sat}}(t)$$

Tunable weights: $\alpha = 0.4$, $\beta = 0.3$, $\gamma = 0.1$, $\delta = 0.2$.

**What it measures.** The reward function is not an evaluation metric in the same sense as the others — it is an internal training signal used only by the DRQN scheduler during learning. It does not appear in the paper's results tables. Instead, it shapes what the DRL agent learns to do, and the results of that learning are evaluated via the seven metrics above.

**Why it is defined here.** The reward function is the single most consequential design decision in any DRL system. Its component weights determine the trade-off the agent learns to make: $\alpha = 0.4$ says grid smoothing is the primary objective, $\beta = 0.3$ says cost is nearly as important, $\delta = 0.2$ says user satisfaction is a secondary objective, and $\gamma = 0.1$ says battery health is the least-weighted but still considered. A reader examining the evaluation results needs to understand these weights to interpret why the DRL scheduler behaves as it does — for example, if TEC is slightly worse than LAVA's but PAR is significantly better, this is the expected outcome given $\alpha > \beta$.

**Connection to the paper's claims.** Each term in the reward function maps directly to one of the paper's evaluation metrics:

| Reward term | Evaluation metric | Weight |
|---|---|---|
| $-\alpha \cdot \Delta\text{PAR}(t)$ | §6.1 PAR | 0.4 — highest priority |
| $-\beta \cdot \text{TEC}(t)$ | §6.2 TEC | 0.3 — second priority |
| $+\delta \cdot \rho_{\text{sat}}(t)$ | §6.3 SoC Satisfaction | 0.2 — third priority |
| $-\gamma \cdot C_{\text{deg}}(t)$ | §6.5 Battery Degradation | 0.1 — lowest priority |

Notably absent from the reward function: scheduling lag (§6.4) and sensing gain (§6.6). These are measured externally and are not objectives the agent optimises directly — they are emergent properties of the system architecture that we validate after training.

**Caveat.** The weights ($\alpha, \beta, \gamma, \delta$) are initial design choices, not results of hyperparameter search. The paper should note that different weight configurations would produce different trade-off profiles. Future work could use Pareto-front analysis to characterise the full space of trade-offs achievable by adjusting these weights.

---

### 6.9 Implementation

| Component | File | Status |
|---|---|---|
| Basic proxy metrics | `integration/metrics.py` | Built (simplified) |
| Full PAR, TEC, scheduling lag | `metrics/evaluator.py` | **Not yet built (Priority 3)** |
| LAVA vs DRL comparison runner | `eval/run_comparison.py` | Built |

---

## Variable Reference

| Symbol | Meaning | Unit |
|---|---|---|
| $\sigma(t)$ | Grid stress | dimensionless $[0,1]$ |
| $\lambda(t)$ | TOU electricity tariff | \$/kWh |
| $\lambda_{\text{V2G}}(t)$ | V2G buy price | \$/kWh |
| $f(t)$ | Grid frequency | Hz |
| $x_k$ | EV position | km |
| $v_k$ | EV speed | km/h |
| $\hat{t}^{\text{arr}}_{k,i}$ | ETA of EV $k$ to station $s_i$ | minutes |
| $\hat{\text{SoC}}_k$ | ISAC-inferred SoC proxy | % |
| $\text{SoC}_k(t)$ | True SoC of EV $k$ at time $t$ | % |
| $\text{SoH}_k$ | Battery state of health | $[0,1]$ |
| $\text{SoC}^{\text{req}}_k$ | Driver-requested SoC at departure | % |
| $T^{\text{dep}}_k$ | Declared departure time | minutes |
| $C_k$ | Usable battery capacity | kWh |
| $P_k(t)$ | Charging (+) or V2G discharge (−) power | kW |
| $P_{\text{grid}}(t)$ | Aggregate station load | kW |
| $P^{\text{V2G}}(t)$ | V2G dispatch power | kW |
| $u_i$ | Station $s_i$ utilisation | $[0,1]$ |
| $q_i$ | Station $s_i$ queue wait | minutes |
| $h_n$ | Hash-chain record digest | SHA-256 |
| $J(s_i)$ | LAVA cost for station $s_i$ | dimensionless |
| $\delta_{\text{route}}$ | Ensemble routing disagreement | $[0,1]$ |
| $\bar{\gamma}$ | Median ensemble confidence | $[0,1]$ |
| $\Delta J$ | Sensing gain | reward units |

---

## Build Priority Mapping

| Priority | Missing Component | Blocks |
|---|---|---|
| P2 | Full SoC/SoH trajectory tracking | Reward function, Evaluation Model |
| P3 | `metrics/evaluator.py` | All paper result figures |
| P4 | `simulation/fast_sim.py` | DRL training (thousands of episodes) |
| P6 | `sensing/soc_proxy.py` | SoC proxy MAE metric, ISAC novelty claim |
| P7 | `contracts/CreditLedger.sol` | Trust Model incentive layer |

*P1 (pluggable scheduler interface) and P5 (DRL scheduler) are complete as of the session ending 2026-05-07.*
