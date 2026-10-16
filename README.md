# Usage

Execute via

```
uv run main.py
```

There is an optional code of block that can be commented out. It will save one response as the raw xml and the parsed json in the `./results/`. Otherwise, parsed data is saved in a temporary directory and cleaned once the ingestion to the ducklake is performed.

The data is loadaed to `./data/broccoli.ducklake.files/` with ducklake catalog `./data/broccoli.ducklake`. Explore via

```
duckdb "ducklake:data/broccoli.ducklake" -ui
```
