from flask import Flask, request, jsonify, render_template_string

from volunteer_graph import build_volunteer_graph

app = Flask(__name__)

# Build the LangGraph app once at startup
volunteer_app = build_volunteer_graph()


@app.route("/volunteer", methods=["POST"])
def volunteer():
    """Run the volunteer graph with JSON input.

    Expected JSON body:
    {
      "location": "City, Country",
      "interests": ["animals", "education"]
    }
    """
    data = request.get_json(force=True, silent=True) or {}

    location = data.get("location")
    if not location:
        return jsonify({"error": "'location' is required"}), 400

    interests = data.get("interests") or []
    if not isinstance(interests, list):
        return jsonify({"error": "'interests' must be a list of strings"}), 400

    state_in = {
        "location": location,
        "interests": interests,
    }

    result = volunteer_app.invoke(state_in)

    return jsonify(result)


HTML_FORM = """
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Volunteer Finder</title>
        <style>
            body { font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; background: #f5f5f7; }
            .card { max-width: 720px; margin: 0 auto; padding: 1.5rem 2rem; background: #fff; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.06); }
            h1 { margin-top: 0; }
            label { display: block; margin-top: 1rem; font-weight: 600; }
            input[type="text"] { width: 100%; padding: 0.5rem 0.75rem; border-radius: 8px; border: 1px solid #ccc; font-size: 1rem; }
            button { margin-top: 1.25rem; padding: 0.6rem 1.2rem; border-radius: 999px; border: none; background: #2563eb; color: #fff; font-size: 1rem; cursor: pointer; }
            button:hover { background: #1d4ed8; }
            .summary { margin-top: 2rem; white-space: pre-wrap; background: #f9fafb; padding: 1rem 1.25rem; border-radius: 8px; border: 1px solid #e5e7eb; }
            .error { margin-top: 1rem; color: #b91c1c; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Volunteer Finder</h1>
            <p>Enter your location and interests to get a tailored summary of volunteer opportunities.</p>
            <form method="post" action="/ui">
                <label for="location">Location</label>
                <input id="location" name="location" type="text" value="{{ location or '' }}" placeholder="e.g. Seattle, WA" required>

                <label for="interests">Interests (comma-separated)</label>
                <input id="interests" name="interests" type="text" value="{{ interests or '' }}" placeholder="animals, education, food">

                <button type="submit">Find opportunities</button>
            </form>

            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}

            {% if summary %}
                <div class="summary">{{ summary }}</div>
            {% endif %}
        </div>
    </body>
    </html>
"""


@app.route("/", methods=["GET"])
def root():
        return jsonify({"status": "ok", "message": "Volunteer graph API", "ui": "/ui"})


@app.route("/ui", methods=["GET", "POST"])
def ui():
        if request.method == "GET":
                return render_template_string(HTML_FORM, location="", interests="", summary=None, error=None)

        # POST: read form fields
        location = request.form.get("location", "").strip()
        interests_str = request.form.get("interests", "").strip()

        if not location:
                return render_template_string(HTML_FORM, location="", interests=interests_str, summary=None, error="Location is required.")

        interests = [s.strip() for s in interests_str.split(",") if s.strip()] if interests_str else []

        state_in = {
                "location": location,
                "interests": interests,
        }

        try:
                result = volunteer_app.invoke(state_in)
                summary = result.get("summary", "(No summary returned.)")
                return render_template_string(HTML_FORM, location=location, interests=interests_str, summary=summary, error=None)
        except Exception as exc:
                return render_template_string(HTML_FORM, location=location, interests=interests_str, summary=None, error=f"Error: {exc}")


if __name__ == "__main__":
    # Basic dev server
    app.run(host="0.0.0.0", port=5001, debug=True)
