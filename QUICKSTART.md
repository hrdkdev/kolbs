# Quick Start

## One-time setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Run the server

```bash
uv run python app.py
```

Open `http://127.0.0.1:7123`.

## Short version

```bash
./run.sh
```

## Common commands

```bash
# create sample data
uv run python -c "import db; db.init_db(); db.seed_sample_data()"

# print database path
uv run python -c "import db; print(db.get_db_path())"

# backup database
cp kolbs.db "kolbs.db.backup-$(date +%Y%m%d-%H%M%S)"
```
