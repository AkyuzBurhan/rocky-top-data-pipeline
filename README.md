# Rocky Top Outfitters — Data Pipeline

Daily data pipeline: ingest the transient `orders.csv` feed, preserve it raw,
clean it, reconcile the product-system migration, enrich with weather, monitor
pipeline health, and produce analytics for:

> Which stores and product categories are most weather-sensitive, and what
> inventory or promotion recommendations follow?

## Status

Built step by step. **Step 0 done:** project skeleton + tooling.

## Setup

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                        # create .venv and install deps
cp credentials.example.json credentials.json   # then fill in real values
```

`credentials.json` is git-ignored — never commit it.

## Layout

```
helpers/   shared package (config, db, io, dq, logs)   [coming next]
src/       pipeline scripts                              [coming next]
sql/       schema                                        [coming next]
data/raw/  preserved daily orders_YYYY-MM-DD.csv files
```
