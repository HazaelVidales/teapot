import json
import os
import re
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path

from flask import Flask, request, jsonify, render_template

from process_oportunities import process_opportunity_files
from volunteer_graph import build_volunteer_graph

app = Flask(__name__)

# Build the LangGraph app once at startup
volunteer_app = build_volunteer_graph()
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "oportunities_raw"
DATA_DIR = BASE_DIR / "oportunities"
SKILLS_PATH = BASE_DIR / "skills.json"
INTEREST_PATH = BASE_DIR / "interest.json"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")


def load_processed_opportunities():

    opportunities = []
    errors = []

    if not DATA_DIR.exists():
        errors.append(f"Directory not found: {DATA_DIR}")
        return opportunities, errors

    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name.endswith(".idx.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"Failed to parse {path.name}: {exc}")
            continue

        stat = path.stat()
        updated_at = datetime.fromtimestamp(stat.st_mtime)
        payload.setdefault("source_file", path.stem)
        payload["file_name"] = path.name
        payload["updated_iso"] = updated_at.isoformat(timespec="seconds")
        payload["updated_display"] = updated_at.strftime("%Y-%m-%d %H:%M")
        payload["_sort_key"] = stat.st_mtime
        opportunities.append(payload)

    opportunities.sort(key=lambda item: item.get("_sort_key", 0), reverse=True)
    return opportunities, errors


def slugify_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-") or "opportunity"
    return value[:60].strip("-") or "opportunity"


def ensure_unique_raw_path(slug: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    candidate = RAW_DIR / f"{slug}.txt"
    counter = 2
    while candidate.exists():
        candidate = RAW_DIR / f"{slug}-{counter}.txt"
        counter += 1
    return candidate


def save_raw_opportunity(title: str, description: str) -> Path:
    slug = slugify_filename(title or "opportunity")
    path = ensure_unique_raw_path(slug)
    path.write_text(description.strip() + "\n", encoding="utf-8")
    return path


def run_processing_pipeline(model_name: str | None = None) -> str:
    model = model_name or DEFAULT_MODEL
    buffer = StringIO()
    with redirect_stdout(buffer):
        process_opportunity_files(
            raw_dir=RAW_DIR,
            output_dir=DATA_DIR,
            skills_path=SKILLS_PATH,
            interests_path=INTEREST_PATH,
            model_name=model,
        )
    return buffer.getvalue().strip()


@app.route("/volunteer", methods=["POST"])
def volunteer():
    """Run the volunteer graph with JSON input.

    Expected JSON body:
    {
      "query": "I live in Seattle and want weekend animal volunteering..."
    }
    """
    data = request.get_json(force=True, silent=True) or {}

    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "'query' is required"}), 400

    state_in = {"query": query}

    result = volunteer_app.invoke(state_in)

    # Return only the structured summary for the UI/client
    return jsonify(result.get("summary", {}))


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "status": "ok",
        "message": "Volunteer graph API",
        "ui": "/ui",
        "processed": "/processed-opportunities",
        "add_raw": "/add-opportunity",
    })


@app.route("/ui", methods=["GET", "POST"])
def ui():
    if request.method == "GET":
        return render_template("ui.html", query="", summary=None, error=None)

    # POST: read form field
    query = request.form.get("query", "").strip()

    if not query:
        return render_template("ui.html", query="", summary=None, error="A query is required.")

    state_in = {"query": query}

    try:
        result = volunteer_app.invoke(state_in)
        summary = result.get("summary")
        return render_template("ui.html", query=query, summary=summary, error=None)
    except Exception as exc:
        return render_template("ui.html", query=query, summary=None, error=f"Error: {exc}")


@app.route("/add-opportunity", methods=["GET", "POST"])
def add_opportunity():
    form_title = ""
    form_description = ""
    errors: list[str] = []
    result = None
    logs = None

    if request.method == "POST":
        form_title = request.form.get("title", "").strip()
        form_description = request.form.get("description", "").strip()

        if not form_title:
            errors.append("A title is required.")
        if not form_description:
            errors.append("Please provide a volunteer opportunity description.")

        if not errors:
            try:
                raw_path = save_raw_opportunity(form_title, form_description)
                logs = run_processing_pipeline()
                processed_path = DATA_DIR / f"{raw_path.stem}.json"
                result = {
                    "raw_file": raw_path.relative_to(BASE_DIR),
                    "processed_file": processed_path.relative_to(BASE_DIR) if processed_path.exists() else None,
                }
                form_title = ""
                form_description = ""
            except Exception as exc:
                errors.append(f"Failed to process opportunity: {exc}")

    return render_template(
        "add_opportunity.html",
        title=form_title,
        description=form_description,
        errors=errors,
        result=result,
        logs=logs,
    )


@app.route("/processed-opportunities", methods=["GET"])
def processed_opportunities():
    opportunities, errors = load_processed_opportunities()
    for entry in opportunities:
        entry.pop("_sort_key", None)
    return render_template(
        "processed.html",
        opportunities=opportunities,
        errors=errors,
    )


if __name__ == "__main__":
    # Basic dev server
    app.run(host="0.0.0.0", port=5001, debug=True)
