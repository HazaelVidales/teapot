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

- Web UI at `/find-opportunity` for entering location and interests
- JSON API at `/volunteer` for programmatic access
- LangGraph-powered workflow for composing the volunteer search and summarization steps
- Uses `requests` and `beautifulsoup4` to fetch and scrape opportunity data

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

Once `app.py` is running, you can either:

- Open the browser UI at `http://localhost:5001/find-opportunity` and submit the form with a location and comma-separated interests, or
- Call the JSON API directly:

```bash
curl -X POST http://localhost:5001/volunteer \
  -H "Content-Type: application/json" \
  -d '{"location": "Seattle, WA", "interests": ["animals", "education"]}'
```

## API

### `POST /volunteer`

JSON endpoint that runs the volunteer LangGraph.

**Request body:**

```json
{
  "location": "Seattle, WA",
  "interests": ["animals", "education"]
}
```

- `location` (string, required): City / area to search in.
- `interests` (array of strings, optional): Topics you care about (e.g. `"food"`, `"education"`).

**Response (example):**

```json
{
  "summary": "...human-friendly summary of relevant volunteer opportunities...",
  "location": "Seattle, WA",
  "interests": ["animals", "education"]
}
```

On error, the API returns a JSON object with an `error` field and an appropriate HTTP status code.

## Configuration

Environment variables:

- `OPENAI_API_KEY` (required): API key used by `langgraph-openai`.

Other configuration, such as which sources to scrape, lives inside the LangGraph builder in `find_opportunity_graph.py`.

## Development

- `app.py` contains the Flask application (`/volunteer` and `/find-opportunity`).
- `find_opportunity_graph.py` defines `build_volunteer_graph()`, which constructs the LangGraph app.
- `test.py` contains basic tests / experiments around the graph or API.

To run the dev server:

```bash
python app.py
```

Then open `http://localhost:5001/find-opportunity` in your browser, or use the `curl` example in the Usage section.