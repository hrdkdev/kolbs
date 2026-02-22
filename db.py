"""
Database models and initialization for Kolb's Learning Cycle app.
Uses SQLite with raw SQL for simplicity.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = os.environ.get("KOLBS_DB_PATH", "kolbs.db")


def get_db_path():
    """Return the absolute path to the database file."""
    return os.path.abspath(DATABASE_PATH)


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT DEFAULT '',
                occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                domain TEXT DEFAULT '',
                valence TEXT DEFAULT 'neutral',
                experience_text TEXT DEFAULT '',
                reflection_text TEXT DEFAULT '',
                reflection_prompts TEXT DEFAULT '{}',
                abstraction_text TEXT DEFAULT '',
                abstraction_prompts TEXT DEFAULT '{}',
                no_experiment_needed INTEGER DEFAULT 0,
                is_complete INTEGER DEFAULT 0,
                current_step INTEGER DEFAULT 1,
                reflects_on_experiment_id INTEGER,
                FOREIGN KEY (reflects_on_experiment_id) REFERENCES experiments(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                status TEXT DEFAULT 'planned',
                start_date DATE,
                review_date DATE,
                outcome_notes TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entry_tags (
                entry_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (entry_id, tag_id),
                FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS entry_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_entry_id INTEGER NOT NULL,
                to_entry_id INTEGER NOT NULL,
                link_type TEXT DEFAULT 'reflects_on',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_entry_id) REFERENCES entries(id) ON DELETE CASCADE,
                FOREIGN KEY (to_entry_id) REFERENCES entries(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_entries_occurred_at ON entries(occurred_at);
            CREATE INDEX IF NOT EXISTS idx_entries_updated_at ON entries(updated_at);
            CREATE INDEX IF NOT EXISTS idx_entries_domain ON entries(domain);
            CREATE INDEX IF NOT EXISTS idx_entries_valence ON entries(valence);
            CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
            CREATE INDEX IF NOT EXISTS idx_experiments_review_date ON experiments(review_date);

            -- High-Propensity Goals tables
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                outcome_target TEXT DEFAULT '',
                target_date DATE,
                target_metric TEXT DEFAULT '',
                is_archived INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS goal_performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_order INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goal_daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                log_date DATE NOT NULL,
                notes TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(goal_id, log_date),
                FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goal_performance_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                daily_log_id INTEGER NOT NULL,
                metric_id INTEGER NOT NULL,
                completed INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (daily_log_id) REFERENCES goal_daily_logs(id) ON DELETE CASCADE,
                FOREIGN KEY (metric_id) REFERENCES goal_performance_metrics(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goal_risks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                risk_description TEXT NOT NULL,
                scripted_action TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_goals_is_archived ON goals(is_archived);
            CREATE INDEX IF NOT EXISTS idx_goal_daily_logs_date ON goal_daily_logs(log_date);
            CREATE INDEX IF NOT EXISTS idx_goal_daily_logs_goal ON goal_daily_logs(goal_id);
        """)


def migrate_db():
    """Run database migrations for schema changes."""
    with get_db() as conn:
        # Check if reflection_prompts column exists
        cursor = conn.execute("PRAGMA table_info(entries)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add reflection_prompts column if it doesn't exist
        if "reflection_prompts" not in columns:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN reflection_prompts TEXT DEFAULT '{}'"
            )
            print("Added reflection_prompts column")

        # Add abstraction_prompts column if it doesn't exist
        if "abstraction_prompts" not in columns:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN abstraction_prompts TEXT DEFAULT '{}'"
            )
            print("Added abstraction_prompts column")


def get_setting(key, default=None):
    """Get a setting value."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    """Set a setting value."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            (key, value),
        )


def get_all_settings():
    """Get all settings as a dict."""
    defaults = {
        "preferred_mode": "wizard",
        "default_domain": "",
        "autosave_enabled": "true",
        "font_size": "medium",
    }
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings = {row["key"]: row["value"] for row in rows}
    for k, v in defaults.items():
        if k not in settings:
            settings[k] = v
    return settings


# Entry CRUD operations


def create_entry(data=None):
    """Create a new entry and return its ID."""
    import json

    data = data or {}
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO entries (
                title, occurred_at, created_at, updated_at, domain, valence,
                experience_text, reflection_text, reflection_prompts,
                abstraction_text, abstraction_prompts,
                no_experiment_needed, is_complete, current_step, reflects_on_experiment_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data.get("title", ""),
                data.get("occurred_at", now),
                now,
                now,
                data.get("domain", ""),
                data.get("valence", "neutral"),
                data.get("experience_text", ""),
                data.get("reflection_text", ""),
                json.dumps(data.get("reflection_prompts", {})),
                data.get("abstraction_text", ""),
                json.dumps(data.get("abstraction_prompts", {})),
                1 if data.get("no_experiment_needed") else 0,
                0,
                data.get("current_step", 1),
                int(data["reflects_on_experiment_id"])
                if data.get("reflects_on_experiment_id")
                and str(data.get("reflects_on_experiment_id")).strip()
                else None,
            ),
        )
        return cursor.lastrowid


def get_entry(entry_id):
    """Get a single entry by ID with its tags and experiments."""
    import json

    with get_db() as conn:
        entry = conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not entry:
            return None
        entry = dict(entry)

        # Parse JSON fields
        if "reflection_prompts" in entry and entry["reflection_prompts"]:
            try:
                entry["reflection_prompts"] = json.loads(entry["reflection_prompts"])
            except (json.JSONDecodeError, TypeError):
                entry["reflection_prompts"] = {}
        else:
            entry["reflection_prompts"] = {}

        if "abstraction_prompts" in entry and entry["abstraction_prompts"]:
            try:
                entry["abstraction_prompts"] = json.loads(entry["abstraction_prompts"])
            except (json.JSONDecodeError, TypeError):
                entry["abstraction_prompts"] = {}
        else:
            entry["abstraction_prompts"] = {}

        # Get tags
        tags = conn.execute(
            """
            SELECT t.id, t.name FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id = ?
        """,
            (entry_id,),
        ).fetchall()
        entry["tags"] = [dict(t) for t in tags]

        # Get experiments
        experiments = conn.execute(
            """
            SELECT * FROM experiments WHERE entry_id = ? ORDER BY created_at
        """,
            (entry_id,),
        ).fetchall()
        entry["experiments"] = [dict(e) for e in experiments]

        # Get linked entry if reflecting on experiment
        if entry["reflects_on_experiment_id"]:
            exp = conn.execute(
                """
                SELECT e.*, en.title as entry_title FROM experiments e
                JOIN entries en ON e.entry_id = en.id
                WHERE e.id = ?
            """,
                (entry["reflects_on_experiment_id"],),
            ).fetchone()
            entry["reflects_on_experiment"] = dict(exp) if exp else None
        else:
            entry["reflects_on_experiment"] = None

        return entry


def update_entry(entry_id, data):
    """Update an entry with partial data."""
    import json

    allowed_fields = [
        "title",
        "occurred_at",
        "domain",
        "valence",
        "experience_text",
        "reflection_text",
        "reflection_prompts",
        "abstraction_text",
        "abstraction_prompts",
        "no_experiment_needed",
        "is_complete",
        "current_step",
        "reflects_on_experiment_id",
    ]

    updates = []
    values = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            value = data[field]
            if field == "no_experiment_needed":
                value = 1 if value else 0
            elif field == "is_complete":
                value = 1 if value else 0
            elif field in ["reflection_prompts", "abstraction_prompts"]:
                value = json.dumps(value) if isinstance(value, dict) else value
            elif field == "reflects_on_experiment_id":
                # Convert empty string to None for foreign key constraint
                value = int(value) if value and str(value).strip() else None
            values.append(value)

    if not updates:
        return

    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(entry_id)

    with get_db() as conn:
        conn.execute(
            f"""
            UPDATE entries SET {", ".join(updates)} WHERE id = ?
        """,
            values,
        )


def delete_entry(entry_id):
    """Delete an entry."""
    with get_db() as conn:
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))


def list_entries(filters=None, sort="newest", limit=50, offset=0):
    """List entries with optional filters."""
    filters = filters or {}
    query = "SELECT * FROM entries WHERE 1=1"
    params = []

    if filters.get("search"):
        query += """ AND (
            title LIKE ? OR experience_text LIKE ? OR 
            reflection_text LIKE ? OR abstraction_text LIKE ?
        )"""
        search = f"%{filters['search']}%"
        params.extend([search, search, search, search])

    if filters.get("domain"):
        query += " AND domain = ?"
        params.append(filters["domain"])

    if filters.get("valence"):
        query += " AND valence = ?"
        params.append(filters["valence"])

    if filters.get("status") == "draft":
        query += " AND is_complete = 0"
    elif filters.get("status") == "complete":
        query += " AND is_complete = 1"

    if filters.get("has_experiments"):
        query += " AND id IN (SELECT DISTINCT entry_id FROM experiments)"

    if filters.get("date_from"):
        query += " AND DATE(occurred_at) >= ?"
        params.append(filters["date_from"])

    if filters.get("date_to"):
        query += " AND DATE(occurred_at) <= ?"
        params.append(filters["date_to"])

    if filters.get("tag"):
        query += """ AND id IN (
            SELECT entry_id FROM entry_tags et
            JOIN tags t ON et.tag_id = t.id
            WHERE t.name = ?
        )"""
        params.append(filters["tag"])

    if filters.get("experiment_status"):
        query += """ AND id IN (
            SELECT entry_id FROM experiments WHERE status = ?
        )"""
        params.append(filters["experiment_status"])

    # Sorting
    if sort == "oldest":
        query += " ORDER BY occurred_at ASC"
    elif sort == "last_edited":
        query += " ORDER BY updated_at DESC"
    else:  # newest
        query += " ORDER BY occurred_at DESC"

    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        entries = conn.execute(query, params).fetchall()
        entries = [dict(e) for e in entries]

        # Get tags for each entry
        for entry in entries:
            tags = conn.execute(
                """
                SELECT t.name FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
            """,
                (entry["id"],),
            ).fetchall()
            entry["tags"] = [t["name"] for t in tags]

            # Get experiment count
            exp_count = conn.execute(
                """
                SELECT COUNT(*) as count FROM experiments WHERE entry_id = ?
            """,
                (entry["id"],),
            ).fetchone()
            entry["experiment_count"] = exp_count["count"]

        return entries


def get_entry_count(filters=None):
    """Get total count of entries matching filters."""
    filters = filters or {}
    query = "SELECT COUNT(*) as count FROM entries WHERE 1=1"
    params = []

    if filters.get("search"):
        query += """ AND (
            title LIKE ? OR experience_text LIKE ? OR 
            reflection_text LIKE ? OR abstraction_text LIKE ?
        )"""
        search = f"%{filters['search']}%"
        params.extend([search, search, search, search])

    if filters.get("domain"):
        query += " AND domain = ?"
        params.append(filters["domain"])

    if filters.get("valence"):
        query += " AND valence = ?"
        params.append(filters["valence"])

    if filters.get("status") == "draft":
        query += " AND is_complete = 0"
    elif filters.get("status") == "complete":
        query += " AND is_complete = 1"

    with get_db() as conn:
        result = conn.execute(query, params).fetchone()
        return result["count"]


def get_latest_draft():
    """Get the most recently updated incomplete entry."""
    with get_db() as conn:
        entry = conn.execute("""
            SELECT * FROM entries WHERE is_complete = 0
            ORDER BY updated_at DESC LIMIT 1
        """).fetchone()
        return dict(entry) if entry else None


def calculate_completion(entry):
    """Calculate completion percentage for an entry."""
    steps = 0
    if entry.get("experience_text"):
        steps += 1
    if entry.get("reflection_text"):
        steps += 1
    if entry.get("abstraction_text"):
        steps += 1
    if entry.get("experiments") and len(entry["experiments"]) > 0:
        steps += 1
    elif entry.get("no_experiment_needed"):
        steps += 1
    return int((steps / 4) * 100)


def get_missing_steps(entry):
    """Get list of missing steps for an entry."""
    missing = []
    if not entry.get("experience_text"):
        missing.append("Experience")
    if not entry.get("reflection_text"):
        missing.append("Reflection")
    if not entry.get("abstraction_text"):
        missing.append("Abstraction")
    if not entry.get("no_experiment_needed"):
        # Check if has experiments
        exp_count = 0
        if "experiments" in entry:
            exp_count = len(entry["experiments"])
        else:
            with get_db() as conn:
                result = conn.execute(
                    "SELECT COUNT(*) as c FROM experiments WHERE entry_id = ?",
                    (entry["id"],),
                ).fetchone()
                exp_count = result["c"]
        if exp_count == 0:
            missing.append("Experimentation")
    return missing


# Experiment CRUD operations


def create_experiment(entry_id, data):
    """Create a new experiment."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO experiments (
                entry_id, text, status, start_date, review_date, 
                outcome_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry_id,
                data.get("text", ""),
                data.get("status", "planned"),
                data.get("start_date"),
                data.get("review_date"),
                data.get("outcome_notes", ""),
                now,
                now,
            ),
        )
        return cursor.lastrowid


def get_experiment(exp_id):
    """Get an experiment by ID."""
    with get_db() as conn:
        exp = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        return dict(exp) if exp else None


def update_experiment(exp_id, data):
    """Update an experiment."""
    allowed_fields = ["text", "status", "start_date", "review_date", "outcome_notes"]
    updates = []
    values = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if not updates:
        return

    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(exp_id)

    with get_db() as conn:
        conn.execute(
            f"""
            UPDATE experiments SET {", ".join(updates)} WHERE id = ?
        """,
            values,
        )


def delete_experiment(exp_id):
    """Delete an experiment."""
    with get_db() as conn:
        conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))


def list_experiments(filters=None, limit=50, offset=0):
    """List all experiments with filters."""
    filters = filters or {}
    query = """
        SELECT e.*, en.title as entry_title, en.id as entry_id
        FROM experiments e
        JOIN entries en ON e.entry_id = en.id
        WHERE 1=1
    """
    params = []

    if filters.get("status"):
        query += " AND e.status = ?"
        params.append(filters["status"])

    if filters.get("entry_id"):
        query += " AND e.entry_id = ?"
        params.append(filters["entry_id"])

    if filters.get("search"):
        query += " AND (e.text LIKE ? OR e.outcome_notes LIKE ?)"
        search = f"%{filters['search']}%"
        params.extend([search, search])

    if filters.get("review_due"):
        query += (
            " AND e.review_date <= DATE('now') AND e.status IN ('planned', 'active')"
        )

    query += " ORDER BY e.review_date ASC NULLS LAST, e.created_at DESC"
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        experiments = conn.execute(query, params).fetchall()
        return [dict(e) for e in experiments]


def get_active_experiments():
    """Get experiments that are planned or active, ordered by review date."""
    with get_db() as conn:
        experiments = conn.execute("""
            SELECT e.*, en.title as entry_title
            FROM experiments e
            JOIN entries en ON e.entry_id = en.id
            WHERE e.status IN ('planned', 'active')
            ORDER BY e.review_date ASC NULLS LAST, e.created_at DESC
        """).fetchall()
        return [dict(e) for e in experiments]


# Tag operations


def get_or_create_tag(name, conn=None):
    """Get a tag by name or create it."""
    name = name.strip().lower()

    def _do(c):
        tag = c.execute("SELECT * FROM tags WHERE name = ?", (name,)).fetchone()
        if tag:
            return tag["id"]
        cursor = c.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        return cursor.lastrowid

    if conn:
        return _do(conn)
    with get_db() as conn:
        return _do(conn)


def set_entry_tags(entry_id, tag_names):
    """Set tags for an entry (replaces existing)."""
    with get_db() as conn:
        conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
        for name in tag_names:
            if name.strip():
                tag_id = get_or_create_tag(name, conn)
                conn.execute(
                    "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                    (entry_id, tag_id),
                )


def get_all_tags():
    """Get all tags with usage count."""
    with get_db() as conn:
        tags = conn.execute("""
            SELECT t.id, t.name, COUNT(et.entry_id) as usage_count
            FROM tags t
            LEFT JOIN entry_tags et ON t.id = et.tag_id
            GROUP BY t.id
            ORDER BY usage_count DESC, t.name ASC
        """).fetchall()
        return [dict(t) for t in tags]


def get_all_domains():
    """Get all unique domains."""
    with get_db() as conn:
        domains = conn.execute("""
            SELECT DISTINCT domain FROM entries 
            WHERE domain != '' ORDER BY domain
        """).fetchall()
        return [d["domain"] for d in domains]


# Entry links


def create_entry_link(from_entry_id, to_entry_id, link_type="reflects_on"):
    """Create a link between entries."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO entry_links (from_entry_id, to_entry_id, link_type)
            VALUES (?, ?, ?)
        """,
            (from_entry_id, to_entry_id, link_type),
        )


def get_entry_links(entry_id):
    """Get all links for an entry."""
    with get_db() as conn:
        links = conn.execute(
            """
            SELECT el.*, e.title as linked_title
            FROM entry_links el
            JOIN entries e ON el.to_entry_id = e.id
            WHERE el.from_entry_id = ?
        """,
            (entry_id,),
        ).fetchall()
        return [dict(l) for l in links]


# Export helpers


def export_entry_as_dict(entry_id):
    """Export a single entry as a dictionary."""
    entry = get_entry(entry_id)
    if not entry:
        return None
    return entry


def export_all_entries():
    """Export all entries as a list of dictionaries."""
    with get_db() as conn:
        entries = conn.execute(
            "SELECT id FROM entries ORDER BY occurred_at DESC"
        ).fetchall()
        return [export_entry_as_dict(e["id"]) for e in entries]


def entry_to_markdown(entry):
    """Convert an entry to Markdown format."""
    lines = []
    lines.append(f"# {entry.get('title') or 'Untitled Entry'}")
    lines.append("")
    lines.append(f"**Date:** {entry.get('occurred_at', '')[:10]}")
    lines.append(f"**Domain:** {entry.get('domain') or 'None'}")
    lines.append(f"**Valence:** {entry.get('valence', 'neutral')}")
    if entry.get("tags"):
        tag_names = [t["name"] if isinstance(t, dict) else t for t in entry["tags"]]
        lines.append(f"**Tags:** {', '.join(tag_names)}")
    lines.append("")

    lines.append("## 1. Experience")
    lines.append(entry.get("experience_text") or "*No experience recorded*")
    lines.append("")

    lines.append("## 2. Reflection")
    lines.append(entry.get("reflection_text") or "*No reflection recorded*")
    lines.append("")

    lines.append("## 3. Abstraction")
    lines.append(entry.get("abstraction_text") or "*No abstraction recorded*")
    lines.append("")

    lines.append("## 4. Experimentation")
    if entry.get("no_experiment_needed"):
        lines.append("*No experiment needed for this entry*")
    elif entry.get("experiments"):
        for exp in entry["experiments"]:
            lines.append(f"### Experiment: {exp.get('text', '')}")
            lines.append(f"- **Status:** {exp.get('status', 'planned')}")
            if exp.get("start_date"):
                lines.append(f"- **Start Date:** {exp['start_date']}")
            if exp.get("review_date"):
                lines.append(f"- **Review Date:** {exp['review_date']}")
            if exp.get("outcome_notes"):
                lines.append(f"- **Outcome:** {exp['outcome_notes']}")
            lines.append("")
    else:
        lines.append("*No experiments recorded*")

    return "\n".join(lines)


# Validation


def validate_experiment_specificity(text):
    """
    Check if experiment text is specific enough.
    Returns (is_valid, warning_message).
    """
    if not text:
        return False, "Experiment text is required"

    text_lower = text.lower()

    # Check for vague phrases
    vague_phrases = [
        "try harder",
        "do better",
        "be more",
        "work on",
        "improve",
        "focus more",
        "remember to",
        "try to",
    ]

    for phrase in vague_phrases:
        if phrase in text_lower and len(text.split()) < 8:
            return True, f"Consider being more specific. What exactly will you do?"

    # Check for action verbs
    action_verbs = [
        "write",
        "create",
        "build",
        "schedule",
        "call",
        "email",
        "set",
        "measure",
        "track",
        "record",
        "practice",
        "read",
        "ask",
        "tell",
        "start",
        "stop",
        "use",
        "implement",
        "test",
        "review",
        "complete",
    ]

    has_verb = any(verb in text_lower for verb in action_verbs)
    if not has_verb and len(text.split()) < 5:
        return True, "Try to include a specific action verb."

    return True, None


def can_mark_complete(entry):
    """Check if an entry can be marked complete."""
    if not entry.get("experience_text"):
        return False, "Experience text is required"
    if not entry.get("reflection_text"):
        return False, "Reflection text is required"
    if not entry.get("abstraction_text"):
        return False, "Abstraction text is required"

    if not entry.get("no_experiment_needed"):
        exp_count = len(entry.get("experiments", []))
        if exp_count == 0:
            return (
                False,
                "At least one experiment is required (or mark 'No experiment needed')",
            )

    return True, None


# Seed data for testing


def seed_sample_data():
    """Create sample data for testing."""
    # Only seed if no entries exist
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM entries").fetchone()["c"]
        if count > 0:
            return

    # Sample entry 1 - Complete
    entry1_id = create_entry(
        {
            "title": "Difficult team meeting",
            "domain": "work",
            "valence": "negative",
            "experience_text": "Had a team meeting where my proposal was rejected. I felt frustrated when colleagues didn't seem to understand my reasoning despite preparing thoroughly.",
            "reflection_text": "- Felt defensive when questions were asked\n- Got impatient explaining details\n- Noticed I was speaking faster than usual\n- Others seemed confused, kept asking for clarification\n- I felt tired before the meeting (late night prior)",
            "abstraction_text": "I tend to assume others have the same context I do. When I'm tired, I skip over foundational explanations. I've noticed this pattern in documentation too - I write for myself, not the reader.",
            "current_step": 4,
        }
    )
    create_experiment(
        entry1_id,
        {
            "text": 'Before next presentation, write a 3-bullet "context summary" for people unfamiliar with the project',
            "status": "active",
            "start_date": "2026-02-15",
            "review_date": "2026-02-25",
        },
    )
    create_experiment(
        entry1_id,
        {
            "text": "Get 7+ hours sleep the night before important meetings",
            "status": "planned",
            "review_date": "2026-03-01",
        },
    )
    set_entry_tags(entry1_id, ["communication", "meetings", "presentations"])
    update_entry(entry1_id, {"is_complete": True})

    # Sample entry 2 - Draft
    entry2_id = create_entry(
        {
            "title": "Morning workout success",
            "domain": "health",
            "valence": "positive",
            "experience_text": "Completed my first 5am workout in months. Felt energized for the rest of the day.",
            "current_step": 2,
        }
    )
    set_entry_tags(entry2_id, ["exercise", "habits"])

    # Sample entry 3 - Quick capture
    entry3_id = create_entry(
        {
            "title": "Debugging insight",
            "domain": "study",
            "valence": "neutral",
            "experience_text": "Spent 2 hours on a bug that was caused by a simple typo. Found it by explaining the code line-by-line to myself.",
            "current_step": 1,
        }
    )
    set_entry_tags(entry3_id, ["debugging", "programming"])

    print("Sample data created successfully.")


# ==========================================
# High-Propensity Goals CRUD operations
# ==========================================

# Goal CRUD


def create_goal(data):
    """Create a new goal and return its ID."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO goals (
                title, description, outcome_target, target_date, 
                target_metric, is_archived, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
        """,
            (
                data.get("title", ""),
                data.get("description", ""),
                data.get("outcome_target", ""),
                data.get("target_date") or None,
                data.get("target_metric", ""),
                now,
                now,
            ),
        )
        return cursor.lastrowid


def get_goal(goal_id):
    """Get a single goal by ID with its metrics, risks, and recent logs."""
    with get_db() as conn:
        goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not goal:
            return None
        goal = dict(goal)

        # Get performance metrics
        metrics = conn.execute(
            """
            SELECT * FROM goal_performance_metrics 
            WHERE goal_id = ? ORDER BY metric_order, id
        """,
            (goal_id,),
        ).fetchall()
        goal["metrics"] = [dict(m) for m in metrics]

        # Get risks
        risks = conn.execute(
            """
            SELECT * FROM goal_risks 
            WHERE goal_id = ? ORDER BY created_at DESC
        """,
            (goal_id,),
        ).fetchall()
        goal["risks"] = [dict(r) for r in risks]

        # Get recent daily logs (last 30 days)
        logs = conn.execute(
            """
            SELECT * FROM goal_daily_logs 
            WHERE goal_id = ? 
            ORDER BY log_date DESC 
            LIMIT 30
        """,
            (goal_id,),
        ).fetchall()
        goal["recent_logs"] = [dict(l) for l in logs]

        return goal


def update_goal(goal_id, data):
    """Update a goal with partial data."""
    allowed_fields = [
        "title",
        "description",
        "outcome_target",
        "target_date",
        "target_metric",
        "is_archived",
    ]

    updates = []
    values = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            value = data[field]
            if field == "is_archived":
                value = 1 if value else 0
            elif field == "target_date" and not value:
                value = None
            values.append(value)

    if not updates:
        return

    updates.append("updated_at = ?")
    values.append(datetime.now().isoformat())
    values.append(goal_id)

    with get_db() as conn:
        conn.execute(
            f"""
            UPDATE goals SET {", ".join(updates)} WHERE id = ?
        """,
            values,
        )


def archive_goal(goal_id):
    """Archive a goal (soft delete)."""
    update_goal(goal_id, {"is_archived": True})


def list_goals(include_archived=False):
    """List all goals."""
    query = "SELECT * FROM goals"
    if not include_archived:
        query += " WHERE is_archived = 0"
    query += " ORDER BY created_at DESC"

    with get_db() as conn:
        goals = conn.execute(query).fetchall()
        result = []
        for goal in goals:
            g = dict(goal)
            # Get metric count
            metric_count = conn.execute(
                "SELECT COUNT(*) as c FROM goal_performance_metrics WHERE goal_id = ?",
                (g["id"],),
            ).fetchone()["c"]
            g["metric_count"] = metric_count

            # Get last log date
            last_log = conn.execute(
                "SELECT log_date FROM goal_daily_logs WHERE goal_id = ? ORDER BY log_date DESC LIMIT 1",
                (g["id"],),
            ).fetchone()
            g["last_log_date"] = last_log["log_date"] if last_log else None

            result.append(g)
        return result


def get_active_goal_count():
    """Get count of active (non-archived) goals."""
    with get_db() as conn:
        result = conn.execute(
            "SELECT COUNT(*) as c FROM goals WHERE is_archived = 0"
        ).fetchone()
        return result["c"]


def can_create_goal():
    """Check if a new goal can be created (max 3 active)."""
    return get_active_goal_count() < 3


# Performance Metrics CRUD


def create_performance_metric(goal_id, metric_name, metric_order=0):
    """Create a new performance metric for a goal."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO goal_performance_metrics (goal_id, metric_name, metric_order)
            VALUES (?, ?, ?)
        """,
            (goal_id, metric_name, metric_order),
        )
        return cursor.lastrowid


def update_performance_metric(metric_id, data):
    """Update a performance metric."""
    allowed_fields = ["metric_name", "metric_order"]
    updates = []
    values = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if not updates:
        return

    values.append(metric_id)

    with get_db() as conn:
        conn.execute(
            f"""
            UPDATE goal_performance_metrics SET {", ".join(updates)} WHERE id = ?
        """,
            values,
        )


def delete_performance_metric(metric_id):
    """Delete a performance metric."""
    with get_db() as conn:
        conn.execute("DELETE FROM goal_performance_metrics WHERE id = ?", (metric_id,))


def get_goal_metrics(goal_id):
    """Get all metrics for a goal."""
    with get_db() as conn:
        metrics = conn.execute(
            """
            SELECT * FROM goal_performance_metrics 
            WHERE goal_id = ? ORDER BY metric_order, id
        """,
            (goal_id,),
        ).fetchall()
        return [dict(m) for m in metrics]


# Goal Risks CRUD


def create_goal_risk(goal_id, risk_description, scripted_action):
    """Create a new risk entry for a goal."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO goal_risks (goal_id, risk_description, scripted_action)
            VALUES (?, ?, ?)
        """,
            (goal_id, risk_description, scripted_action),
        )
        return cursor.lastrowid


def update_goal_risk(risk_id, data):
    """Update a risk entry."""
    allowed_fields = ["risk_description", "scripted_action"]
    updates = []
    values = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if not updates:
        return

    values.append(risk_id)

    with get_db() as conn:
        conn.execute(
            f"""
            UPDATE goal_risks SET {", ".join(updates)} WHERE id = ?
        """,
            values,
        )


def delete_goal_risk(risk_id):
    """Delete a risk entry."""
    with get_db() as conn:
        conn.execute("DELETE FROM goal_risks WHERE id = ?", (risk_id,))


def get_goal_risks(goal_id):
    """Get all risks for a goal."""
    with get_db() as conn:
        risks = conn.execute(
            """
            SELECT * FROM goal_risks 
            WHERE goal_id = ? ORDER BY created_at DESC
        """,
            (goal_id,),
        ).fetchall()
        return [dict(r) for r in risks]


# Daily Logs CRUD


def create_or_update_daily_log(goal_id, log_date, notes=""):
    """Create or update a daily log entry."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        # Check if log exists
        existing = conn.execute(
            "SELECT id FROM goal_daily_logs WHERE goal_id = ? AND log_date = ?",
            (goal_id, log_date),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE goal_daily_logs 
                SET notes = ?, updated_at = ?
                WHERE id = ?
            """,
                (notes, now, existing["id"]),
            )
            return existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO goal_daily_logs (goal_id, log_date, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (goal_id, log_date, notes, now, now),
            )
            return cursor.lastrowid


def get_daily_log(goal_id, log_date):
    """Get a daily log with its performance entries."""
    with get_db() as conn:
        log = conn.execute(
            """
            SELECT * FROM goal_daily_logs 
            WHERE goal_id = ? AND log_date = ?
        """,
            (goal_id, log_date),
        ).fetchone()

        if not log:
            return None

        log = dict(log)

        # Get performance entries
        entries = conn.execute(
            """
            SELECT pe.*, pm.metric_name 
            FROM goal_performance_entries pe
            JOIN goal_performance_metrics pm ON pe.metric_id = pm.id
            WHERE pe.daily_log_id = ?
            ORDER BY pm.metric_order, pm.id
        """,
            (log["id"],),
        ).fetchall()
        log["entries"] = [dict(e) for e in entries]

        return log


def get_daily_logs_for_goal(goal_id, limit=90):
    """Get daily logs for a goal (for calendar view)."""
    with get_db() as conn:
        logs = conn.execute(
            """
            SELECT dl.*, 
                   COUNT(pe.id) as entry_count,
                   SUM(CASE WHEN pe.completed = 1 THEN 1 ELSE 0 END) as completed_count
            FROM goal_daily_logs dl
            LEFT JOIN goal_performance_entries pe ON dl.id = pe.daily_log_id
            WHERE dl.goal_id = ?
            GROUP BY dl.id
            ORDER BY dl.log_date DESC
            LIMIT ?
        """,
            (goal_id, limit),
        ).fetchall()
        return [dict(l) for l in logs]


# Performance Entries CRUD


def save_performance_entry(daily_log_id, metric_id, completed, rating=0, notes=""):
    """Save or update a performance entry."""
    with get_db() as conn:
        # Check if entry exists
        existing = conn.execute(
            """
            SELECT id FROM goal_performance_entries 
            WHERE daily_log_id = ? AND metric_id = ?
        """,
            (daily_log_id, metric_id),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE goal_performance_entries 
                SET completed = ?, rating = ?, notes = ?
                WHERE id = ?
            """,
                (1 if completed else 0, rating, notes, existing["id"]),
            )
            return existing["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO goal_performance_entries 
                (daily_log_id, metric_id, completed, rating, notes)
                VALUES (?, ?, ?, ?, ?)
            """,
                (daily_log_id, metric_id, 1 if completed else 0, rating, notes),
            )
            return cursor.lastrowid


def save_daily_log_with_entries(goal_id, log_date, entries, notes=""):
    """Save a complete daily log with all performance entries."""
    log_id = create_or_update_daily_log(goal_id, log_date, notes)

    for entry in entries:
        save_performance_entry(
            log_id,
            entry["metric_id"],
            entry.get("completed", False),
            entry.get("rating", 0),
            entry.get("notes", ""),
        )

    return log_id


# ==========================================
# Goal Statistics and Streak Calculations
# ==========================================


def calculate_goal_streak(goal_id):
    """
    Calculate the current streak for a goal.
    Uses 'Never Miss Twice' rule: streak only breaks if you miss 2+ days in a row.
    """
    from datetime import date, timedelta

    with get_db() as conn:
        # Get all log dates ordered by date desc
        logs = conn.execute(
            """
            SELECT log_date FROM goal_daily_logs 
            WHERE goal_id = ? 
            ORDER BY log_date DESC
        """,
            (goal_id,),
        ).fetchall()

        if not logs:
            return 0

        log_dates = set(log["log_date"] for log in logs)
        today = date.today()
        streak = 0
        consecutive_misses = 0
        check_date = today

        while True:
            date_str = check_date.isoformat()

            if date_str in log_dates:
                streak += 1
                consecutive_misses = 0
            else:
                consecutive_misses += 1
                # Never miss twice: allow one miss, but two misses break streak
                if consecutive_misses >= 2:
                    break

            check_date -= timedelta(days=1)

            # Don't go back more than 365 days
            if (today - check_date).days > 365:
                break

        return streak


def get_goal_completion_rate(goal_id, days=30):
    """Calculate completion rate for the last N days."""
    from datetime import date, timedelta

    start_date = (date.today() - timedelta(days=days)).isoformat()

    with get_db() as conn:
        # Get total metrics for the goal
        metric_count = conn.execute(
            "SELECT COUNT(*) as c FROM goal_performance_metrics WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()["c"]

        if metric_count == 0:
            return 0

        # Get completed entries in the date range
        result = conn.execute(
            """
            SELECT 
                COUNT(DISTINCT dl.log_date) as logged_days,
                SUM(CASE WHEN pe.completed = 1 THEN 1 ELSE 0 END) as completed_count,
                COUNT(pe.id) as total_entries
            FROM goal_daily_logs dl
            LEFT JOIN goal_performance_entries pe ON dl.id = pe.daily_log_id
            WHERE dl.goal_id = ? AND dl.log_date >= ?
        """,
            (goal_id, start_date),
        ).fetchone()

        if result["total_entries"] == 0:
            return 0

        return int((result["completed_count"] / result["total_entries"]) * 100)


def get_goal_calendar_data(goal_id, days=90):
    """Get calendar heat map data for a goal."""
    from datetime import date, timedelta

    start_date = (date.today() - timedelta(days=days)).isoformat()

    with get_db() as conn:
        # Get metric count
        metric_count = conn.execute(
            "SELECT COUNT(*) as c FROM goal_performance_metrics WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()["c"]

        # Get daily completion data
        logs = conn.execute(
            """
            SELECT 
                dl.log_date,
                COUNT(pe.id) as entry_count,
                SUM(CASE WHEN pe.completed = 1 THEN 1 ELSE 0 END) as completed_count,
                AVG(CASE WHEN pe.completed = 1 THEN pe.rating ELSE NULL END) as avg_rating
            FROM goal_daily_logs dl
            LEFT JOIN goal_performance_entries pe ON dl.id = pe.daily_log_id
            WHERE dl.goal_id = ? AND dl.log_date >= ?
            GROUP BY dl.log_date
            ORDER BY dl.log_date DESC
        """,
            (goal_id, start_date),
        ).fetchall()

        # Build calendar data
        calendar = {}
        for log in logs:
            completion = 0
            if metric_count > 0 and log["completed_count"]:
                completion = log["completed_count"] / metric_count
            calendar[log["log_date"]] = {
                "completion": completion,
                "avg_rating": log["avg_rating"] or 0,
                "logged": True,
            }

        return calendar


def get_goals_dashboard_stats():
    """Get aggregate statistics for the goals dashboard."""
    with get_db() as conn:
        active_count = conn.execute(
            "SELECT COUNT(*) as c FROM goals WHERE is_archived = 0"
        ).fetchone()["c"]

        archived_count = conn.execute(
            "SELECT COUNT(*) as c FROM goals WHERE is_archived = 1"
        ).fetchone()["c"]

        # Get total logs this week
        from datetime import date, timedelta

        week_start = (date.today() - timedelta(days=7)).isoformat()
        logs_this_week = conn.execute(
            """
            SELECT COUNT(DISTINCT goal_id || '-' || log_date) as c 
            FROM goal_daily_logs 
            WHERE log_date >= ?
        """,
            (week_start,),
        ).fetchone()["c"]

        return {
            "active_count": active_count,
            "archived_count": archived_count,
            "logs_this_week": logs_this_week,
            "can_create": active_count < 3,
        }
