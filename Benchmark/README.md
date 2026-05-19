# Benchmark: Fakhrooeian & Pitz 2023 V2G Scheduling

This folder implements the benchmark scheduling scenarios and paper-pattern comparison from:

> P. Fakhrooeian and V. Pitz, "Scheduling the charging and discharging events of electric vehicles for quasi dynamic load flow calculations of a low-voltage distribution grid with regard to stochastic behavior and grid requirements," Electric Power Systems Research, 2023.

## What Is Implemented

The implementation reproduces the paper's four benchmark scheduling cases and the scheduling equations that are implementable without DIgSILENT:

1. **Scenario 1: Worst-case uncontrolled charging**
   - EVs arrive during peak hours and charge immediately until the desired SoC is reached.

2. **Scenario 2: V2G without grid-operator control**
   - EVs may discharge during peak hours down to the user minimum SoC, then charge after peak hours.

3. **Scenario 3: V2G with grid-operator start-time control**
   - EVs discharge during peak hours and are then split into staggered overnight charging groups using full available charging power.

4. **Scenario 4: V2G with grid-operator control and limited charging power**
   - EVs discharge during peak hours and are then charged with reduced power in staggered groups.

## Important Scope Note

The original paper evaluates the schedules in DIgSILENT PowerFactory on a low-voltage feeder. This repo does not include DIgSILENT, the proprietary feeder model, or BDEW load-profile exports. Therefore this implementation reproduces the **stochastic EV scheduling logic and comparable output tables** using a deterministic low-voltage feeder proxy:

- repeated stochastic EV arrival and SoC draws,
- aggregate feeder load profile,
- thermal loading proxy,
- active power loss proxy,
- voltage-drop proxy.

The strongest defensible comparison is against **Table 2 total-load trends** and the Fig. 5 load-profile pattern. Tables 3-5 are included as published reference targets, but our loading, loss, and voltage values are proxy-supported until a real load-flow model is added.

The runner performs repeated stochastic trials by default and writes both aggregate and per-run outputs. Use the aggregate files for Fig. 5 and Table 2-style reporting.

## Paper Values Used

- Table 1 simulation parameters.
- Table 2 total-load min/avg/max values.
- Table 3 maximum-line-loading min/avg/max values.
- Table 4 power-loss min/avg/max values.
- Table 5 voltage min/avg/max values.
- Equations 8-10 for charge timing and SoC update.
- Equations 11-14 for discharge power and SoC update.

Published reference values are stored in:

```text
Benchmark/paper_reference_values.json
```

## Run

```powershell
python -m Benchmark.run_fakhrooeian_pitz --output-dir reports\benchmark_fakhrooeian_pitz --seed 2026 --runs 30
```

Outputs:

- `scenario_summary.csv`
- `scenario_run_summary.csv`
- `scenario_summary.json`
- `timeseries.csv`
- `timeseries_runs.csv`
- `ev_sessions.csv`
- `README_RESULTS.md`
- `PATTERN_REPORT.md`

Plot the Fig. 5-style load profile comparison:

```powershell
python -m Benchmark.plot_fakhrooeian_pitz --report-dir reports\benchmark_fakhrooeian_pitz --output-dir reports\benchmark_fakhrooeian_pitz\figures
```
