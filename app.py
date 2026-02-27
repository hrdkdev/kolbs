"""
Kolb's Experiential Learning Cycle - Flask Application
A local-only web app for completing daily Kolb learning cycles.
"""

import json
import os
import io
import zipfile
import shutil
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
    Response,
)

import db

app = Flask(__name__)
app.secret_key = os.environ.get(
    "KOLBS_SECRET_KEY", "dev-secret-key-change-in-production"
)

# Initialize database on startup
with app.app_context():
    db.init_db()
    db.migrate_db()


# Template context processors
@app.context_processor
def inject_globals():
    """Inject global variables into all templates."""
    settings = db.get_all_settings()
    return {"settings": settings, "now": datetime.now()}


# Helper functions
def get_filters_from_request():
    """Extract filter parameters from request."""
    return {
        "search": request.args.get("search", "").strip(),
        "domain": request.args.get("domain", ""),
        "valence": request.args.get("valence", ""),
        "status": request.args.get("status", ""),
        "tag": request.args.get("tag", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to": request.args.get("date_to", ""),
        "has_experiments": request.args.get("has_experiments") == "1",
        "experiment_status": request.args.get("experiment_status", ""),
    }


# HTML Routes


@app.route("/")
def index():
    """Home dashboard."""
    # Get recent entries (no status filtering)
    recent_entries = db.list_entries(limit=10)
    for entry in recent_entries:
        entry["completion"] = db.calculate_completion(entry)

    active_experiments = db.get_active_experiments()

    return render_template(
        "index.html",
        recent_entries=recent_entries,
        active_experiments=active_experiments,
    )


@app.route("/new")
def new_entry():
    """Create new entry page."""
    mode = request.args.get("mode", db.get_setting("preferred_mode", "wizard"))
    quick = request.args.get("quick") == "1"
    from_experiment = request.args.get("from_experiment")

    # Get available experiments to reflect on
    available_experiments = db.get_active_experiments()

    # Pre-fill if reflecting on experiment
    prefill = {}
    if from_experiment:
        exp = db.get_experiment(int(from_experiment))
        if exp:
            prefill["reflects_on_experiment_id"] = exp["id"]
            prefill["reflects_on_experiment"] = exp
            prefill["reflection_prompts"] = {}
            prefill["abstraction_prompts"] = {}

    domains = db.get_all_domains()
    tags = db.get_all_tags()

    return render_template(
        "entry_form.html",
        entry=prefill,
        mode=mode,
        quick=quick,
        is_new=True,
        domains=domains,
        tags=tags,
        available_experiments=available_experiments,
    )


@app.route("/entry/<int:entry_id>")
def view_entry(entry_id):
    """View/edit entry page."""
    entry = db.get_entry(entry_id)
    if not entry:
        flash("Entry not found", "error")
        return redirect(url_for("index"))

    mode = request.args.get("mode", db.get_setting("preferred_mode", "wizard"))
    entry["completion"] = db.calculate_completion(entry)
    entry["missing_steps"] = db.get_missing_steps(entry)

    domains = db.get_all_domains()
    tags = db.get_all_tags()
    available_experiments = db.get_active_experiments()

    return render_template(
        "entry_form.html",
        entry=entry,
        mode=mode,
        is_new=False,
        domains=domains,
        tags=tags,
        available_experiments=available_experiments,
    )


@app.route("/entry/<int:entry_id>/delete", methods=["POST"])
def delete_entry(entry_id):
    """Delete an entry."""
    db.delete_entry(entry_id)
    flash("Entry deleted", "success")
    return redirect(url_for("index"))


@app.route("/entries")
def list_entries():
    """List all entries with filters."""
    filters = get_filters_from_request()
    sort = request.args.get("sort", "newest")
    page = int(request.args.get("page", 1))
    per_page = 20

    entries = db.list_entries(
        filters=filters, sort=sort, limit=per_page, offset=(page - 1) * per_page
    )

    for entry in entries:
        entry["completion"] = db.calculate_completion(entry)

    total = db.get_entry_count(filters)
    total_pages = (total + per_page - 1) // per_page

    domains = db.get_all_domains()
    tags = db.get_all_tags()

    return render_template(
        "entries.html",
        entries=entries,
        filters=filters,
        sort=sort,
        page=page,
        total_pages=total_pages,
        total=total,
        domains=domains,
        tags=tags,
    )


@app.route("/experiments")
def list_experiments():
    """List all experiments."""
    filters = {
        "status": request.args.get("status", ""),
        "search": request.args.get("search", ""),
        "review_due": request.args.get("review_due") == "1",
    }

    experiments = db.list_experiments(filters=filters, limit=100)

    return render_template("experiments.html", experiments=experiments, filters=filters)


@app.route("/export")
def export_page():
    """Export options page."""
    entries = db.list_entries(limit=1000)
    return render_template("export.html", entries=entries)


@app.route("/export/entry/<int:entry_id>/markdown")
def export_entry_markdown(entry_id):
    """Export single entry as Markdown."""
    entry = db.get_entry(entry_id)
    if not entry:
        flash("Entry not found", "error")
        return redirect(url_for("export_page"))

    markdown = db.entry_to_markdown(entry)
    filename = f"kolb-{entry_id}-{entry.get('title', 'untitled')[:30]}.md"
    filename = "".join(c for c in filename if c.isalnum() or c in ".-_ ")

    return Response(
        markdown,
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/export/entry/<int:entry_id>/json")
def export_entry_json(entry_id):
    """Export single entry as JSON."""
    entry = db.get_entry(entry_id)
    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    return Response(
        json.dumps(entry, indent=2, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="kolb-{entry_id}.json"'},
    )


@app.route("/export/all/zip")
def export_all_zip():
    """Export all entries as ZIP."""
    entries = db.export_all_entries()

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add JSON dump of all entries
        zf.writestr("all-entries.json", json.dumps(entries, indent=2, default=str))

        # Add individual Markdown files
        for entry in entries:
            markdown = db.entry_to_markdown(entry)
            title = entry.get("title", "untitled")[:30]
            title = "".join(c for c in title if c.isalnum() or c in ".-_ ")
            filename = f"entries/{entry['id']:04d}-{title}.md"
            zf.writestr(filename, markdown)

    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"kolbs-export-{timestamp}.zip",
    )


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """Settings page."""
    if request.method == "POST":
        db.set_setting("preferred_mode", request.form.get("preferred_mode", "wizard"))
        db.set_setting("default_domain", request.form.get("default_domain", ""))
        db.set_setting(
            "autosave_enabled", request.form.get("autosave_enabled", "false")
        )
        db.set_setting("font_size", request.form.get("font_size", "medium"))
        flash("Settings saved", "success")
        return redirect(url_for("settings_page"))

    settings = db.get_all_settings()
    domains = db.get_all_domains()
    db_path = db.get_db_path()

    return render_template(
        "settings.html", settings=settings, domains=domains, db_path=db_path
    )


@app.route("/settings/backup", methods=["POST"])
def create_backup():
    """Create a backup of the database."""
    src = db.get_db_path()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"{src}.backup-{timestamp}"

    try:
        shutil.copy2(src, dst)
        flash(f"Backup created: {dst}", "success")
    except Exception as e:
        flash(f"Backup failed: {str(e)}", "error")

    return redirect(url_for("settings_page"))


@app.route("/seed-data", methods=["POST"])
def seed_data():
    """Seed sample data for testing."""
    db.seed_sample_data()
    flash("Sample data created", "success")
    return redirect(url_for("index"))


# Form submission routes (non-JS fallback)


@app.route("/entry/create", methods=["POST"])
def create_entry_form():
    """Create entry via form submission."""
    data = {
        "title": request.form.get("title", ""),
        "occurred_at": request.form.get("occurred_at", datetime.now().isoformat()),
        "domain": request.form.get("domain", ""),
        "valence": request.form.get("valence", "neutral"),
        "experience_text": request.form.get("experience_text", ""),
        "reflection_text": request.form.get("reflection_text", ""),
        "abstraction_text": request.form.get("abstraction_text", ""),
        "no_experiment_needed": request.form.get("no_experiment_needed") == "on",
        "current_step": int(request.form.get("current_step", 1)),
        "reflects_on_experiment_id": request.form.get("reflects_on_experiment_id")
        or None,
    }

    # Handle prompt responses from JSON if provided (API calls)
    if request.is_json or request.form.get("reflection_prompts"):
        data["reflection_prompts"] = (
            json.loads(request.form.get("reflection_prompts", "{}"))
            if not request.is_json
            else request.json.get("reflection_prompts", {})
        )
        data["abstraction_prompts"] = (
            json.loads(request.form.get("abstraction_prompts", "{}"))
            if not request.is_json
            else request.json.get("abstraction_prompts", {})
        )

    entry_id = db.create_entry(data)

    # Handle tags
    tags_str = request.form.get("tags", "")
    if tags_str:
        tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
        db.set_entry_tags(entry_id, tag_names)

    flash("Entry created", "success")
    return redirect(url_for("view_entry", entry_id=entry_id))


@app.route("/entry/<int:entry_id>/update", methods=["POST"])
def update_entry_form(entry_id):
    """Update entry via form submission."""
    data = {
        "title": request.form.get("title", ""),
        "occurred_at": request.form.get("occurred_at"),
        "domain": request.form.get("domain", ""),
        "valence": request.form.get("valence", "neutral"),
        "experience_text": request.form.get("experience_text", ""),
        "reflection_text": request.form.get("reflection_text", ""),
        "abstraction_text": request.form.get("abstraction_text", ""),
        "no_experiment_needed": request.form.get("no_experiment_needed") == "on",
        "current_step": int(request.form.get("current_step", 1)),
        "reflects_on_experiment_id": request.form.get("reflects_on_experiment_id")
        or None,
    }

    # Handle prompt responses from JSON if provided (API calls)
    if request.is_json or request.form.get("reflection_prompts"):
        data["reflection_prompts"] = (
            json.loads(request.form.get("reflection_prompts", "{}"))
            if not request.is_json
            else request.json.get("reflection_prompts", {})
        )
        data["abstraction_prompts"] = (
            json.loads(request.form.get("abstraction_prompts", "{}"))
            if not request.is_json
            else request.json.get("abstraction_prompts", {})
        )

    db.update_entry(entry_id, data)

    # Handle tags
    tags_str = request.form.get("tags", "")
    tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
    db.set_entry_tags(entry_id, tag_names)

    flash("Entry saved", "success")

    # Handle navigation
    next_step = request.form.get("next_step")
    if next_step:
        return redirect(url_for("view_entry", entry_id=entry_id, step=next_step))

    return redirect(url_for("view_entry", entry_id=entry_id))


@app.route("/entry/<int:entry_id>/experiment/add", methods=["POST"])
def add_experiment_form(entry_id):
    """Add experiment via form submission."""
    data = {
        "text": request.form.get("text", ""),
        "status": request.form.get("status", "planned"),
        "start_date": request.form.get("start_date") or None,
        "review_date": request.form.get("review_date") or None,
        "outcome_notes": request.form.get("outcome_notes", ""),
    }

    # Validate specificity
    is_valid, warning = db.validate_experiment_specificity(data["text"])
    if warning:
        flash(warning, "warning")

    exp_id = db.create_experiment(entry_id, data)
    flash("Experiment added", "success")

    return redirect(url_for("view_entry", entry_id=entry_id))


@app.route("/experiment/<int:exp_id>/update", methods=["POST"])
def update_experiment_form(exp_id):
    """Update experiment via form submission."""
    exp = db.get_experiment(exp_id)
    if not exp:
        flash("Experiment not found", "error")
        return redirect(url_for("list_experiments"))

    data = {
        "text": request.form.get("text", ""),
        "status": request.form.get("status", "planned"),
        "start_date": request.form.get("start_date") or None,
        "review_date": request.form.get("review_date") or None,
        "outcome_notes": request.form.get("outcome_notes", ""),
    }

    db.update_experiment(exp_id, data)
    flash("Experiment updated", "success")

    # Return to referrer or experiments list
    referrer = request.form.get("referrer", url_for("list_experiments"))
    return redirect(referrer)


@app.route("/experiment/<int:exp_id>/delete", methods=["POST"])
def delete_experiment_form(exp_id):
    """Delete experiment via form submission."""
    exp = db.get_experiment(exp_id)
    entry_id = exp["entry_id"] if exp else None

    db.delete_experiment(exp_id)
    flash("Experiment deleted", "success")

    if entry_id:
        return redirect(url_for("view_entry", entry_id=entry_id))
    return redirect(url_for("list_experiments"))


# API Routes (JSON endpoints for autosave)


@app.route("/api/entry", methods=["POST"])
def api_create_entry():
    """Create a new entry via API."""
    data = request.get_json() or {}

    entry_id = db.create_entry(data)

    if data.get("tags"):
        db.set_entry_tags(entry_id, data["tags"])

    entry = db.get_entry(entry_id)
    return jsonify({"success": True, "entry": entry, "id": entry_id})


@app.route("/api/entry/<int:entry_id>", methods=["PATCH"])
def api_update_entry(entry_id):
    """Update entry via API (partial update)."""
    data = request.get_json() or {}

    entry = db.get_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "Entry not found"}), 404

    db.update_entry(entry_id, data)

    if "tags" in data:
        db.set_entry_tags(entry_id, data["tags"])

    updated_entry = db.get_entry(entry_id)
    updated_entry["completion"] = db.calculate_completion(updated_entry)

    return jsonify(
        {
            "success": True,
            "entry": updated_entry,
            "saved_at": datetime.now().isoformat(),
        }
    )


@app.route("/api/entry/<int:entry_id>/complete", methods=["POST"])
def api_mark_complete(entry_id):
    """Mark entry as complete via API."""
    entry = db.get_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "Entry not found"}), 404

    can_complete, msg = db.can_mark_complete(entry)
    if not can_complete:
        return jsonify({"success": False, "error": msg}), 400

    db.update_entry(entry_id, {"is_complete": True})

    return jsonify({"success": True, "message": "Entry marked complete"})


@app.route("/api/entry/<int:entry_id>/experiment", methods=["POST"])
def api_add_experiment(entry_id):
    """Add experiment to entry via API."""
    data = request.get_json() or {}

    entry = db.get_entry(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "Entry not found"}), 404

    is_valid, warning = db.validate_experiment_specificity(data.get("text", ""))

    exp_id = db.create_experiment(entry_id, data)
    experiment = db.get_experiment(exp_id)

    return jsonify({"success": True, "experiment": experiment, "warning": warning})


@app.route("/api/experiment/<int:exp_id>", methods=["PATCH"])
def api_update_experiment(exp_id):
    """Update experiment via API."""
    data = request.get_json() or {}

    exp = db.get_experiment(exp_id)
    if not exp:
        return jsonify({"success": False, "error": "Experiment not found"}), 404

    warning = None
    if "text" in data:
        _, warning = db.validate_experiment_specificity(data["text"])

    db.update_experiment(exp_id, data)
    updated = db.get_experiment(exp_id)

    return jsonify({"success": True, "experiment": updated, "warning": warning})


@app.route("/api/experiment/<int:exp_id>", methods=["DELETE"])
def api_delete_experiment(exp_id):
    """Delete experiment via API."""
    exp = db.get_experiment(exp_id)
    if not exp:
        return jsonify({"success": False, "error": "Experiment not found"}), 404

    db.delete_experiment(exp_id)

    return jsonify({"success": True})


@app.route("/api/tag", methods=["POST"])
def api_create_tag():
    """Create or get tag via API."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()

    if not name:
        return jsonify({"success": False, "error": "Tag name required"}), 400

    tag_id = db.get_or_create_tag(name)

    return jsonify({"success": True, "tag": {"id": tag_id, "name": name.lower()}})


@app.route("/api/tags")
def api_list_tags():
    """List all tags."""
    tags = db.get_all_tags()
    return jsonify({"tags": tags})


@app.route("/api/domains")
def api_list_domains():
    """List all domains."""
    domains = db.get_all_domains()
    return jsonify({"domains": domains})


@app.route("/api/experiments/active")
def api_active_experiments():
    """Get active experiments."""
    experiments = db.get_active_experiments()
    return jsonify({"experiments": experiments})


# ==========================================
# Goals HTML Routes
# ==========================================


@app.route("/goals")
def goals_dashboard():
    """Goals dashboard page."""
    goals = db.list_goals(include_archived=False)
    archived_goals = db.list_goals(include_archived=True)
    archived_goals = [g for g in archived_goals if g.get("is_archived")]

    # Add streak and completion rate for each goal
    for goal in goals:
        goal["streak"] = db.calculate_goal_streak(goal["id"])
        goal["completion_rate"] = db.get_goal_completion_rate(goal["id"])

    stats = db.get_goals_dashboard_stats()

    return render_template(
        "goals_dashboard.html",
        goals=goals,
        archived_goals=archived_goals,
        stats=stats,
    )


@app.route("/goals/new")
def new_goal():
    """Create new goal page."""
    if not db.can_create_goal():
        flash(
            "Maximum 3 active goals allowed. Archive a goal to create a new one.",
            "warning",
        )
        return redirect(url_for("goals_dashboard"))

    return render_template("goal_form.html", goal=None, is_new=True)


@app.route("/goals/<int:goal_id>")
def view_goal(goal_id):
    """View/edit goal page with tabbed interface."""
    goal = db.get_goal(goal_id)
    if not goal:
        flash("Goal not found", "error")
        return redirect(url_for("goals_dashboard"))

    tab = request.args.get("tab", "outcome")
    goal["streak"] = db.calculate_goal_streak(goal_id)
    goal["completion_rate"] = db.get_goal_completion_rate(goal_id)
    goal["calendar_data"] = db.get_goal_calendar_data(goal_id)

    return render_template(
        "goal_view.html",
        goal=goal,
        tab=tab,
    )


@app.route("/goals/<int:goal_id>/edit")
def edit_goal(goal_id):
    """Edit goal page."""
    goal = db.get_goal(goal_id)
    if not goal:
        flash("Goal not found", "error")
        return redirect(url_for("goals_dashboard"))

    return render_template("goal_form.html", goal=goal, is_new=False)


@app.route("/goals/<int:goal_id>/log")
@app.route("/goals/<int:goal_id>/log/<log_date>")
def goal_daily_log(goal_id, log_date=None):
    """Daily performance logging page."""
    from datetime import date

    goal = db.get_goal(goal_id)
    if not goal:
        flash("Goal not found", "error")
        return redirect(url_for("goals_dashboard"))

    if not log_date:
        log_date = date.today().isoformat()

    existing_log = db.get_daily_log(goal_id, log_date)
    metrics = db.get_goal_metrics(goal_id)

    # Build entries map for existing values
    entries_map = {}
    if existing_log and existing_log.get("entries"):
        for entry in existing_log["entries"]:
            entries_map[entry["metric_id"]] = entry

    return render_template(
        "goal_daily_log.html",
        goal=goal,
        log_date=log_date,
        existing_log=existing_log,
        metrics=metrics,
        entries_map=entries_map,
    )


# Goals Form Submission Routes


@app.route("/goals/create", methods=["POST"])
def create_goal_form():
    """Create goal via form submission."""
    if not db.can_create_goal():
        flash("Maximum 3 active goals allowed.", "error")
        return redirect(url_for("goals_dashboard"))

    data = {
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "outcome_target": request.form.get("outcome_target", "").strip(),
        "target_date": request.form.get("target_date") or None,
        "target_metric": request.form.get("target_metric", "").strip(),
    }

    if not data["title"]:
        flash("Title is required", "error")
        return redirect(url_for("new_goal"))

    goal_id = db.create_goal(data)

    # Handle metrics (comma-separated or multiple inputs)
    metrics_str = request.form.get("metrics", "")
    if metrics_str:
        metric_names = [m.strip() for m in metrics_str.split(",") if m.strip()]
        for i, name in enumerate(metric_names):
            db.create_performance_metric(goal_id, name, i)

    flash("Goal created successfully", "success")
    return redirect(url_for("view_goal", goal_id=goal_id))


@app.route("/goals/<int:goal_id>/update", methods=["POST"])
def update_goal_form(goal_id):
    """Update goal via form submission."""
    data = {
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "outcome_target": request.form.get("outcome_target", "").strip(),
        "target_date": request.form.get("target_date") or None,
        "target_metric": request.form.get("target_metric", "").strip(),
    }

    db.update_goal(goal_id, data)
    flash("Goal updated", "success")
    return redirect(url_for("view_goal", goal_id=goal_id))


@app.route("/goals/<int:goal_id>/archive", methods=["POST"])
def archive_goal_route(goal_id):
    """Archive a goal."""
    db.archive_goal(goal_id)
    flash("Goal archived", "success")
    return redirect(url_for("goals_dashboard"))


@app.route("/goals/<int:goal_id>/unarchive", methods=["POST"])
def unarchive_goal_route(goal_id):
    """Unarchive a goal."""
    if not db.can_create_goal():
        flash("Maximum 3 active goals. Archive another goal first.", "warning")
        return redirect(url_for("goals_dashboard"))

    db.update_goal(goal_id, {"is_archived": False})
    flash("Goal restored", "success")
    return redirect(url_for("goals_dashboard"))


@app.route("/goals/<int:goal_id>/delete", methods=["POST"])
def delete_goal_route(goal_id):
    """Permanently delete a goal."""
    db.delete_goal(goal_id)
    flash("Goal permanently deleted", "success")
    return redirect(url_for("goals_dashboard"))


@app.route("/goals/<int:goal_id>/metric/add", methods=["POST"])
def add_metric_form(goal_id):
    """Add a performance metric to a goal."""
    metric_name = request.form.get("metric_name", "").strip()
    if not metric_name:
        flash("Metric name is required", "error")
        return redirect(url_for("view_goal", goal_id=goal_id, tab="performance"))

    # Get current max order
    metrics = db.get_goal_metrics(goal_id)
    max_order = max([m["metric_order"] for m in metrics], default=-1)

    db.create_performance_metric(goal_id, metric_name, max_order + 1)
    flash("Metric added", "success")
    return redirect(url_for("view_goal", goal_id=goal_id, tab="performance"))


@app.route("/goals/metric/<int:metric_id>/delete", methods=["POST"])
def delete_metric_form(metric_id):
    """Delete a performance metric."""
    # Get goal_id before deletion
    with db.get_db() as conn:
        metric = conn.execute(
            "SELECT goal_id FROM goal_performance_metrics WHERE id = ?",
            (metric_id,),
        ).fetchone()
        goal_id = metric["goal_id"] if metric else None

    db.delete_performance_metric(metric_id)
    flash("Metric deleted", "success")

    if goal_id:
        return redirect(url_for("view_goal", goal_id=goal_id, tab="performance"))
    return redirect(url_for("goals_dashboard"))


@app.route("/goals/<int:goal_id>/risk/add", methods=["POST"])
def add_risk_form(goal_id):
    """Add a risk to a goal."""
    risk_description = request.form.get("risk_description", "").strip()
    scripted_action = request.form.get("scripted_action", "").strip()

    if not risk_description or not scripted_action:
        flash("Both risk and scripted action are required", "error")
        return redirect(url_for("view_goal", goal_id=goal_id, tab="risks"))

    db.create_goal_risk(goal_id, risk_description, scripted_action)
    flash("Risk added", "success")
    return redirect(url_for("view_goal", goal_id=goal_id, tab="risks"))


@app.route("/goals/risk/<int:risk_id>/delete", methods=["POST"])
def delete_risk_form(risk_id):
    """Delete a risk."""
    # Get goal_id before deletion
    with db.get_db() as conn:
        risk = conn.execute(
            "SELECT goal_id FROM goal_risks WHERE id = ?",
            (risk_id,),
        ).fetchone()
        goal_id = risk["goal_id"] if risk else None

    db.delete_goal_risk(risk_id)
    flash("Risk deleted", "success")

    if goal_id:
        return redirect(url_for("view_goal", goal_id=goal_id, tab="risks"))
    return redirect(url_for("goals_dashboard"))


@app.route("/goals/<int:goal_id>/log/save", methods=["POST"])
def save_daily_log_form(goal_id):
    """Save daily log via form submission."""
    from datetime import date

    log_date = request.form.get("log_date", date.today().isoformat())
    notes = request.form.get("notes", "").strip()

    metrics = db.get_goal_metrics(goal_id)
    entries = []

    for metric in metrics:
        metric_id = metric["id"]
        completed = request.form.get(f"completed_{metric_id}") == "on"
        rating_str = request.form.get(f"rating_{metric_id}", "0")
        try:
            rating = int(rating_str) if rating_str else 0
        except ValueError:
            rating = 0
        entry_notes = request.form.get(f"notes_{metric_id}", "").strip()

        entries.append(
            {
                "metric_id": metric_id,
                "completed": completed,
                "rating": rating,
                "notes": entry_notes,
            }
        )

    db.save_daily_log_with_entries(goal_id, log_date, entries, notes)
    flash("Daily log saved", "success")
    return redirect(url_for("view_goal", goal_id=goal_id, tab="performance"))


# ==========================================
# Goals API Routes
# ==========================================


@app.route("/api/goal", methods=["POST"])
def api_create_goal():
    """Create a new goal via API."""
    if not db.can_create_goal():
        return jsonify(
            {"success": False, "error": "Maximum 3 active goals allowed"}
        ), 400

    data = request.get_json() or {}
    goal_id = db.create_goal(data)

    # Handle metrics
    if data.get("metrics"):
        for i, name in enumerate(data["metrics"]):
            db.create_performance_metric(goal_id, name, i)

    goal = db.get_goal(goal_id)
    return jsonify({"success": True, "goal": goal, "id": goal_id})


@app.route("/api/goal/<int:goal_id>", methods=["PATCH"])
def api_update_goal(goal_id):
    """Update goal via API."""
    data = request.get_json() or {}

    goal = db.get_goal(goal_id)
    if not goal:
        return jsonify({"success": False, "error": "Goal not found"}), 404

    db.update_goal(goal_id, data)
    updated_goal = db.get_goal(goal_id)

    return jsonify(
        {
            "success": True,
            "goal": updated_goal,
            "saved_at": datetime.now().isoformat(),
        }
    )


@app.route("/api/goal/<int:goal_id>/metric", methods=["POST"])
def api_add_metric(goal_id):
    """Add metric via API."""
    data = request.get_json() or {}
    metric_name = data.get("metric_name", "").strip()

    if not metric_name:
        return jsonify({"success": False, "error": "Metric name required"}), 400

    metrics = db.get_goal_metrics(goal_id)
    max_order = max([m["metric_order"] for m in metrics], default=-1)

    metric_id = db.create_performance_metric(goal_id, metric_name, max_order + 1)

    return jsonify(
        {
            "success": True,
            "metric_id": metric_id,
            "metric_name": metric_name,
        }
    )


@app.route("/api/goal/metric/<int:metric_id>", methods=["DELETE"])
def api_delete_metric(metric_id):
    """Delete metric via API."""
    db.delete_performance_metric(metric_id)
    return jsonify({"success": True})


@app.route("/api/goal/<int:goal_id>/risk", methods=["POST"])
def api_add_risk(goal_id):
    """Add risk via API."""
    data = request.get_json() or {}
    risk_description = data.get("risk_description", "").strip()
    scripted_action = data.get("scripted_action", "").strip()

    if not risk_description or not scripted_action:
        return jsonify({"success": False, "error": "Both fields required"}), 400

    risk_id = db.create_goal_risk(goal_id, risk_description, scripted_action)

    return jsonify(
        {
            "success": True,
            "risk_id": risk_id,
        }
    )


@app.route("/api/goal/risk/<int:risk_id>", methods=["DELETE"])
def api_delete_risk(risk_id):
    """Delete risk via API."""
    db.delete_goal_risk(risk_id)
    return jsonify({"success": True})


@app.route("/api/goal/<int:goal_id>/log", methods=["POST"])
def api_save_daily_log(goal_id):
    """Save daily log via API."""
    from datetime import date

    data = request.get_json() or {}
    log_date = data.get("log_date", date.today().isoformat())
    notes = data.get("notes", "")
    entries = data.get("entries", [])

    log_id = db.save_daily_log_with_entries(goal_id, log_date, entries, notes)

    # Return updated stats
    streak = db.calculate_goal_streak(goal_id)
    completion_rate = db.get_goal_completion_rate(goal_id)

    return jsonify(
        {
            "success": True,
            "log_id": log_id,
            "streak": streak,
            "completion_rate": completion_rate,
        }
    )


@app.route("/api/goal/<int:goal_id>/calendar")
def api_goal_calendar(goal_id):
    """Get calendar data for a goal."""
    days = request.args.get("days", 90, type=int)
    calendar_data = db.get_goal_calendar_data(goal_id, days)
    return jsonify({"calendar": calendar_data})


# Error handlers


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", error="Page not found", code=404), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", error="Server error", code=500), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=7123)
