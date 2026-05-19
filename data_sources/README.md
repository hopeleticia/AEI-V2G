# Real Grid Load Data Sources

## CAISO Demand Trend

Primary source: California ISO Today's Outlook demand chart data.

- Current demand CSV: `https://www.caiso.com/outlook/current/demand.csv`
- Historical demand CSV pattern: `https://www.caiso.com/outlook/history/YYYYMMDD/demand.csv`
- Source page: `https://www.caiso.com/todays-outlook/`

The CSV includes 5-minute values for:

- `Day ahead forecast`
- `Hour ahead forecast`
- `Current demand`
- `Demand response`

CAISO notes that Today's Outlook demand and net-demand trend data are informational and exclude dispatchable pump loads and battery charging load. For journal wording, cite these as public operational demand-trend data from CAISO, not billing-grade settlement data.

## Local Dataset Format

The downloader writes normalized CSV files under `data/grid_profiles/`:

```csv
timestamp,date,time,day_ahead_forecast_mw,hour_ahead_forecast_mw,current_demand_mw,demand_response_mw,source
2024-05-01T00:00:00,2024-05-01,00:00,21938,21728,21568,,CAISO
```

Use:

```powershell
python -m data_sources.download_caiso_load --start 2024-05-01 --end 2024-05-07 --output data/grid_profiles/caiso_2024-05-01_2024-05-07.csv
```
