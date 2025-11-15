import json
import os
import re
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path

from flask import Flask, request, jsonify, render_template

from process_oportunities import process_opportunity_files
from find_opportunity_graph import build_volunteer_graph

app = Flask(__name__)

# Build the LangGraph app once at startup
volunteer_app = build_volunteer_graph()
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "oportunities_raw"
DATA_DIR = BASE_DIR / "oportunities"
INDEX_DIR = BASE_DIR / "index"
SKILLS_PATH = BASE_DIR / "skill.json"
INTEREST_PATH = BASE_DIR / "interest.json"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")


def load_processed_opportunities():

    opportunities = []
    errors = []

    if not DATA_DIR.exists():
        errors.append(f"Directory not found: {DATA_DIR}")
        return opportunities, errors

    for path in sorted(DATA_DIR.glob("*.json")):
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


def load_json_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def load_index(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    index = payload.get("index")
    return index if isinstance(index, dict) else {}


def extract_intent(query: str, skills: list[str], interests: list[str]) -> dict[str, list[str]]:
    lowered = query.lower()

    def match_terms(terms: list[str]) -> list[str]:
        matches: list[str] = []
        for term in terms:
            token = term.strip()
            if not token:
                continue
            if token.lower() in lowered and token not in matches:
                matches.append(token)
        return matches

    return {
        "skills": match_terms(skills),
        "interests": match_terms(interests),
    }


def consolidate_matches(intent: dict[str, list[str]], limit: int = 10) -> dict:
    skill_index = load_index(INDEX_DIR / "skill.idx.json")
    interest_index = load_index(INDEX_DIR / "interest.idx.json")
    combined: dict[str, dict] = {}

    def register(entry: dict[str, str], term: str, category: str, weight: float) -> None:
        file_name = entry.get("file")
        if not file_name:
            return
        match = combined.setdefault(file_name, {
            "title": entry.get("title", file_name),
            "file": file_name,
            "source_file": entry.get("source_file", file_name),
            "score": 0.0,
            "skills": [],
            "interests": [],
        })
        match[category].append(term)
        match["score"] += weight

    for skill in intent.get("skills", []):
        for entry in skill_index.get(skill, []):
            register(entry, skill, "skills", 2.0)

    for interest in intent.get("interests", []):
        for entry in interest_index.get(interest, []):
            register(entry, interest, "interests", 1.5)

    results = []
    for file_name, info in combined.items():
        data = {}
        try:
            data = json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))
        except Exception:
            data = {}
        results.append({
            **info,
            "details": {
                "description": data.get("description"),
                "skills": data.get("skills", []),
                "interests": data.get("interests", []),
                "model": data.get("model"),
                "source_excerpt": data.get("source_excerpt"),
            },
        })

    ordered = sorted(results, key=lambda item: (-item["score"], item["title"].lower()))
    return {
        "items": ordered[: max(limit, 1)],
        "available": len(ordered),
    }


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
    links = [
        {"path": "/find-opportunity", "label": "Find Opportunities", "description": "Run the LangGraph workflow via the interactive form."},
        {"path": "/processed-opportunities", "label": "Processed Dataset", "description": "Browse all processed opportunities with metadata."},
        {"path": "/add-opportunity", "label": "Add Opportunity", "description": "Paste a new description and rerun the processor."},
        {"path": "/find-opportunity", "label": "Intent Match API", "description": "POST endpoint that matches text queries to the indexed dataset."},
        {"path": "/volunteer", "label": "LangGraph API", "description": "POST endpoint that runs the GPT-5.1 summarization flow."},
    ]
    return render_template("hub.html", links=links)


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
        "add-opportunity.html",
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


@app.route("/find-opportunity", methods=["GET", "POST"])
def find_opportunity():
    if request.method == "GET":
        return render_template("find-opportunity.html", query="", summary=None, error=None)

    if request.is_json or (request.mimetype and "json" in request.mimetype):
        data = request.get_json(force=True, silent=True) or {}
        query = str(data.get("query", "")).strip()
        try:
            limit = int(data.get("limit", 8))
        except (TypeError, ValueError):
            limit = 8
        limit = max(1, min(limit, 25))

        if not query:
            return jsonify({"error": "'query' is required"}), 400

        skills = load_json_list(SKILLS_PATH)
        interests = load_json_list(INTEREST_PATH)
        intent = extract_intent(query, skills, interests)
        match_data = consolidate_matches(intent, limit=limit)

        return jsonify({
            "query": query,
            "intent": intent,
            "matches": match_data["items"],
            "stats": {
                "requested_limit": limit,
                "available_matches": match_data["available"],
                "skill_terms": len(intent.get("skills", [])),
                "interest_terms": len(intent.get("interests", [])),
            },
        })

    query = request.form.get("query", "").strip()
    if not query:
        return render_template("find-opportunity.html", query="", summary=None, error="A query is required.")

    state_in = {"query": query}

    try:
        result = volunteer_app.invoke(state_in)
        summary = result.get("summary")
        return render_template("find-opportunity.html", query=query, summary=summary, error=None)
    except Exception as exc:
        return render_template("find-opportunity.html", query=query, summary=None, error=f"Error: {exc}")


if __name__ == "__main__":
    # Basic dev server
    app.run(host="0.0.0.0", port=5001, debug=True)
