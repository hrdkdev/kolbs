# Kolb's Reader

Local Flask app for working through a simplified four-stage Kolb worksheet.

## Run with uv

1. Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Sync dependencies:

```bash
uv sync
```

3. Start the server:

```bash
uv run python app.py
```

4. Open:

```text
http://127.0.0.1:7123
```

You can also use:

```bash
./run.sh
```

That script runs `uv sync` and then starts the app.

## Project files

```text
kolbs/
  app.py
  db.py
  pyproject.toml
  run.sh
  kolbs.db
  templates/
  static/
```

## Useful commands

```bash
# start the app
uv run python app.py

# create sample data
uv run python -c "import db; db.init_db(); db.seed_sample_data()"

# show database path
uv run python -c "import db; print(db.get_db_path())"
```

## Environment variables

- `KOLBS_DB_PATH`: custom SQLite path, default `kolbs.db`
- `KOLBS_SECRET_KEY`: Flask session secret
