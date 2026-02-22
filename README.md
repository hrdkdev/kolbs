# Kolb's Experiential Learning Cycle App

A local-only web application for completing daily Kolb learning cycles. Built with Python/Flask and SQLite.

## Features

- **Guided Wizard Mode**: Step-by-step flow through Experience, Reflection, Abstraction, Experimentation
- **Power Mode**: Edit all four steps on one page with accordion sections
- **Quick Capture**: Start entries fast with minimal friction
- **Autosave**: Changes saved automatically with visual indicator
- **Experiments Tracking**: Create, track, and review specific action experiments
- **Search and Filters**: Find entries by keywords, tags, domains, dates, status
- **Export**: Download entries as Markdown or JSON, bulk export as ZIP
- **Keyboard Shortcuts**: Ctrl+S to save, Ctrl+Enter for next step, / to search
- **Distraction-free Mode**: Hide navigation for focused writing
- **No external dependencies**: All CSS/JS shipped locally, no CDNs

## Requirements

- Python 3.8+
- No external services required

## Setup

1. **Install dependencies with uv**:

   ```bash
   # Install uv if you don't have it
   # curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv pip install -r requirements.txt
   ```

2. **Run the application**:

   ```bash
   # Quick start (recommended)
   ./run.sh

   # Or manually
   uv run python app.py

   # Or using Flask CLI
   uv run flask run --port 7123
   ```

3. **Open in browser**: http://127.0.0.1:7123

## Database

- **Location**: `kolbs.db` in the project directory
- **Custom location**: Set the `KOLBS_DB_PATH` environment variable
- **Auto-created**: Database tables are created automatically on first run

## Backup

### Manual Backup

Copy the `kolbs.db` file to a safe location:

```bash
cp kolbs.db kolbs.db.backup
```

### In-App Backup

Go to Settings > Database > "Create Backup Copy" to create a timestamped backup.

## Export

### Single Entry

1. Go to /export
2. Choose an entry and click "Markdown" or "JSON"

### All Entries

1. Go to /export
2. Click "Download ZIP" to get all entries as Markdown files plus a JSON dump

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save current entry |
| Ctrl+Enter | Next step (wizard mode) |
| / | Focus search input |
| Esc | Exit focus mode / close modals |

## Project Structure

```
kolbs/
  app.py              # Flask application and routes
  db.py               # Database models and operations
  requirements.txt    # Python dependencies
  kolbs.db            # SQLite database (auto-created)
  templates/
    base.html         # Base template
    index.html        # Home dashboard
    entry_form.html   # Entry create/edit (wizard + power mode)
    entries.html      # Entries list with filters
    experiments.html  # Experiments list
    export.html       # Export options
    settings.html     # Settings page
    error.html        # Error page
  static/
    css/
      style.css       # All styles
    js/
      main.js         # Autosave, shortcuts, accordions
```

## Configuration

Settings are stored in the database and can be changed via /settings:

- **Preferred Mode**: wizard or power
- **Default Domain**: Pre-fill domain for new entries
- **Autosave**: Enable/disable automatic saving
- **Font Size**: small, medium, or large

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KOLBS_DB_PATH` | Path to SQLite database file | `kolbs.db` |
| `KOLBS_SECRET_KEY` | Flask secret key for sessions | dev key (change in production) |

## Sample Data

To create sample entries for testing:

1. Go to Settings
2. Click "Create Sample Data"

Or via command line:

```bash
uv run python -c "import db; db.init_db(); db.seed_sample_data()"
```

## API Endpoints

For programmatic access or custom integrations:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/entry` | Create new entry |
| PATCH | `/api/entry/<id>` | Update entry (partial) |
| POST | `/api/entry/<id>/complete` | Mark entry complete |
| POST | `/api/entry/<id>/experiment` | Add experiment |
| PATCH | `/api/experiment/<id>` | Update experiment |
| DELETE | `/api/experiment/<id>` | Delete experiment |
| POST | `/api/tag` | Create/get tag |
| GET | `/api/tags` | List all tags |
| GET | `/api/domains` | List all domains |
| GET | `/api/experiments/active` | Get active experiments |

## Kolb's Learning Cycle

This app implements the four stages of Kolb's Experiential Learning Cycle:

1. **Experience**: Concrete experience - what happened?
2. **Reflection**: Reflective observation - how did you observe it?
3. **Abstraction**: Abstract conceptualization - what patterns emerge?
4. **Experimentation**: Active experimentation - what will you try differently?

Each step should lead logically to the next. The goal is to transform experience into actionable learning.

## License

MIT
