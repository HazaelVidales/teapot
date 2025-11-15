# Teapot

Teapot is a small Flask web app that uses a LangGraph workflow (built with `langgraph`, `langgraph-openai`, and `langchain-core`) to find and summarize volunteer opportunities based on a user's location and interests. It exposes both a simple HTML form UI and a JSON API.

## Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [API](#api)
- [Configuration](#configuration)
- [Development](#development)

## About

The app builds a volunteer "graph" using `langgraph` and `langgraph-openai`, then uses `requests` and `beautifulsoup4` to gather and parse online volunteer listings. A Flask application (`app.py`) exposes an endpoint that runs the graph and returns a concise, human-readable summary of relevant opportunities for a given location and set of interests.

## Features

- Landing hub at `/` with quick links to every workflow surface
- Unified `/find-opportunity` route (HTML + JSON) that runs the LangGraph finder
- Processed dataset viewer at `/processed-opportunities` plus a writer UI at `/add-opportunity`
- Automated processing script (`process_oportunities.py`) that turns `oportunities_raw/*.txt` into structured JSON under `oportunities/`
- Skill and interest indexes in `index/skill.idx.json` and `index/interest.idx.json` for fast intent matching
- `/volunteer` LangGraph API for long-form GPT-5.1 summaries of the requested opportunities

## Installation

### Tech stack

This project uses:

- `langgraph` and `langgraph-openai` for the volunteer recommendation workflow
- `langchain-core` for core prompt/LLM abstractions used inside the graph
- `flask` for the HTTP API and simple HTML UI
- `requests` and `beautifulsoup4` for fetching and scraping volunteer opportunity data

### Prerequisites

- Python 3.10+ (recommended)
- An OpenAI-compatible API key (for `langgraph-openai`), exported as e.g. `OPENAI_API_KEY`
- `pip` (or `pipx`) for installing dependencies

### Setup (local environment)

Create and activate a virtual environment:

```bash
cd teapot

python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install flask langgraph langgraph-openai langchain-core requests beautifulsoup4
```

Set your OpenAI-compatible API key (example for macOS / Linux):

```bash
export OPENAI_API_KEY="sk-..."
```

You can put this `export` line into your shell profile (e.g. `~/.zshrc`) if you want it to persist.

Run the development server:

```bash
python app.py
```

The UI will be available at `http://localhost:5001/find-opportunity` and the JSON API at `http://localhost:5001/volunteer`.

## Usage

### Basic Usage

1. **Generate (or refresh) the dataset.** Populate `oportunities_raw/*.txt` and run:

   ```bash
   python process_oportunities.py
   ```

   This produces structured JSON under `oportunities/` and the aggregated indexes in `index/`.

2. **Explore via the finder UI.** Open `http://localhost:5001/find-opportunity` to describe what you need (location, skills, interests, timing). Use `/add-opportunity` to paste new descriptions and rerun the processor without leaving the browser.

3. **Call the JSON APIs.**

   - Intent matching with the index-backed endpoint:

     ```bash
     curl -X POST http://localhost:5001/find-opportunity \
       -H "Content-Type: application/json" \
       -d '{"query": "Weekend gardening mentor", "limit": 5}'
     ```

   - Full LangGraph summary via GPT-5.1:

     ```bash
     curl -X POST http://localhost:5001/volunteer \
       -H "Content-Type: application/json" \
       -d '{"query": "I live in Seattle and love animal rescues"}'
     ```

## API

### `GET | POST /find-opportunity`

- `GET` renders the interactive finder UI.
- `POST` with JSON returns index-backed matches:

  ```json
  {
    "query": "weekend animal rescue volunteer",
    "limit": 5
  }
  ```

  - `query` (string, required): Natural-language description of what you want.
  - `limit` (int, optional, default `8`, max `25`): Number of matches to return.

  Response payload:

  ```json
  {
    "query": "weekend animal rescue volunteer",
    "intent": {"skills": ["animal care"], "interests": ["shelter support"]},
    "matches": [
      {
        "title": "PAWS Playtime Pal",
        "file": "paws_playtime_pal.json",
        "skills": ["animal care"],
        "interests": ["shelter support"],
        "score": 5.0,
        "details": {"description": "...", "skills": [...], "interests": [...], "model": "gpt-5.1"}
      }
    ],
    "stats": {"requested_limit": 5, "available_matches": 3, "skill_terms": 1, "interest_terms": 1}
  }
  ```

### `POST /volunteer`

Runs the GPT-5.1 LangGraph summarizer for a single `query` string.

```json
{
  "query": "I live in Seattle, love education nonprofits, and need Saturday shifts"
}
```

Response:

```json
{
  "summary": {
    "overview": "...",
    "items": [{
      "title": "Girls STEM Lab",
      "org": "Northside Community Center",
      "why_fit": "...",
      "time": "Saturdays 10am-1pm",
      "location": "Seattle, WA",
      "tags": ["education", "mentoring"],
      "url": "https://example.org/stem",
      "phone": null,
      "contact_email": null,
      "suggested_introduction": "..."
    }]
  }
}
```

Errors return an `error` field with an appropriate HTTP status.

## Configuration

Environment variables:

- `OPENAI_API_KEY` (required): API key used by `langgraph-openai`.

Other configuration, such as which sources to scrape, lives inside the LangGraph builder in `find_opportunity_graph.py`.

## Development

- `app.py` contains the Flask application (`/volunteer`, `/find-opportunity`, `/processed-opportunities`, etc.).
- `find_opportunity_graph.py` defines `build_volunteer_graph()`, which constructs the LangGraph app.
- `process_oportunities.py` converts `oportunities_raw/*.txt` into structured JSON under `oportunities/` and creates the skill/interest index files under `index/`.
- `templates/find-opportunity.html`, `templates/processed.html`, and `templates/add_opportunity.html` power the browser experiences.
- `test.py` contains basic tests / experiments around the graph or API.

To run the dev server:

```bash
python app.py
```

Then open `http://localhost:5001/find-opportunity` in your browser, or use the `curl` examples in the Usage section.