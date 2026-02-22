# Quick Start Guide

## Running the App

```bash
./run.sh
```

Then open http://127.0.0.1:7123

## Using uv

All commands should be run with `uv run` prefix:

```bash
# Run the app
uv run python app.py

# Run with Flask CLI
uv run flask run --port 7123

# Initialize database
uv run python -c "import db; db.init_db()"

# Create sample data
uv run python -c "import db; db.init_db(); db.seed_sample_data()"

# Run Python shell with app context
uv run python
```

## Common Tasks

### Create a backup
```bash
cp kolbs.db kolbs.db.backup-$(date +%Y%m%d-%H%M%S)
```

### Reset database (WARNING: deletes all data)
```bash
rm kolbs.db
uv run python -c "import db; db.init_db(); db.seed_sample_data()"
```

### Check database location
```bash
uv run python -c "import db; print(db.get_db_path())"
```

### Export all data
Visit http://127.0.0.1:7123/export and click "Download ZIP"

## Development

### Install new dependencies
```bash
# Add to requirements.txt first, then:
uv pip install -r requirements.txt
```

### Run tests
```bash
uv run python -c "
from app import app
with app.test_client() as client:
    assert client.get('/').status_code == 200
    print('Tests passed!')
"
```

## Environment Variables

```bash
# Custom database location
export KOLBS_DB_PATH=/path/to/custom.db
uv run python app.py

# Custom secret key
export KOLBS_SECRET_KEY=your-secret-key-here
uv run python app.py
```

## Keyboard Shortcuts

- `Ctrl+S` - Save
- `Ctrl+Enter` - Next step
- `/` - Focus search
- `Esc` - Exit focus mode
