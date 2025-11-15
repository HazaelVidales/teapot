from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

class VolunteerState(TypedDict, total=False):
    query: str
    validated: bool
    location: str
    interests: List[str]
    skills: List[str]
    raw_results: List[Dict]
    ranked_results: List[Dict]
    summary: str


def parse_user_query(state: VolunteerState) -> VolunteerState:
    query = state.get("query", "").strip()

    if not query:
        return {
            "validated": False,
            "location": state.get("location", ""),
            "interests": state.get("interests", []),
            "skills": state.get("skills", []),
        }
    prompt = f"""
You extract structured info from a user query about volunteering.

User query:
---
{query}
---

Return ONLY valid JSON with this exact shape:
{{
    "location": string,              // city + state or region (empty string if none)
    "interests": [string, ...],      // 0+ short interest topics
    "skills": [string, ...],         // 0+ relevant skills
    "validated": boolean             // true if this is a reasonable volunteer request
}}

Rules:
- Keep interests and skills short (1–3 words each).
- If something is unclear, leave it out instead of guessing wildly.
"""

    llm_resp = llm.invoke(prompt)

    import json

    try:
        parsed = json.loads(llm_resp.content)
        if not isinstance(parsed, dict):
            raise ValueError("Expected dict")
    except Exception:
        # Fallback: treat as invalid but pass through existing fields
        parsed = {}

    location = parsed.get("location") or state.get("location", "")
    interests = parsed.get("interests") or state.get("interests", [])
    skills = parsed.get("skills") or state.get("skills", [])
    validated = bool(parsed.get("validated", False))

    return {
        "location": location,
        "interests": interests,
        "skills": skills,
        "validated": validated,
    }

def create_query_parameters(state: VolunteerState) -> VolunteerState:
    location = state.get("location", "Seattle, WA")
    interests = state.get("interests", [])
    return {
        "location": location,
        "interests": interests,
        "skills": []
    }

def search_volunteer_opportunities(state: VolunteerState) -> VolunteerState:
    location = state["location"]
    interests = state.get("interests", [])
    
    # Use LLM to propose 5 tailored opportunities (structured JSON)
    interests_text = ", ".join(interests) if interests else "not specified"

    prompt = f"""
You are a helpful assistant that suggests real-world style volunteer opportunities.

User location: {location}
User interests: {interests_text}

Return a JSON list (array) of up to 5 volunteer opportunities.
Each opportunity MUST be an object with the following keys:
- "title" (string)
- "org" (string)
- "description" (string)
- "location" (string)
- "time" (short human phrase, e.g. "Weekends", "Weekdays 3-6pm")
- "tags" (array of short strings)
- "url" (string, can be a plausible URL if unknown)

Respond with ONLY valid JSON, no extra commentary.
"""

    llm_resp = llm.invoke(prompt)

    try:
        import json

        opps = json.loads(llm_resp.content)
        if not isinstance(opps, list):
            raise ValueError("LLM did not return a list")
    except Exception:
        # Fallback: no opportunities if LLM output is invalid
        opps = []

    # Ensure location field is filled in
    for opp in opps:
        if not opp.get("location"):
            opp["location"] = location

    return {"raw_results": opps}

def rank_opportunities(state: VolunteerState) -> VolunteerState:
    interests = [i.lower() for i in state.get("interests", [])]
    results = state.get("raw_results", [])

    def score(opp):
        tags = " ".join(opp.get("tags", [])).lower()
        s = 0
        for i in interests:
            if i in tags:
                s += 2
        # simple heuristic: more tags = slightly higher score
        s += len(opp.get("tags", [])) * 0.1
        return s

    ranked = sorted(results, key=score, reverse=True)
    return {"ranked_results": ranked}

llm = ChatOpenAI(model="gpt-5.1")

def summarize_results(state: VolunteerState) -> VolunteerState:
    location = state["location"]
    interests = state.get("interests", [])
    ranked = state.get("ranked_results", [])

    if not ranked:
        return {
            "summary": {
                "overview": f"No volunteer opportunities found near {location} for interests {interests}.",
                "items": []
            }
        }

    lines = []
    for i, opp in enumerate(ranked[:5], start=1):
        lines.append(
            f"{i}. title={opp['title']} | org={opp['org']} | "
            f"time={opp['time']} | location={opp.get('location', location)} | "
            f"tags={', '.join(opp.get('tags', []))} | url={opp['url']}"
        )
    listing = "\n".join(lines)

    prompt = f"""
You are helping someone find volunteer opportunities.

Location: {location}
Interests: {', '.join(interests) if interests else 'not specified'}

Here are the options (one per line with fields):

{listing}

Return ONLY valid JSON with this exact shape:
{{
  "overview": string,
  "items": [
    {{
      "title": string,
      "org": string,
      "why_fit": string,
      "time": string,
      "location": string,
      "tags": [string, ...],
          "url": string,
          "phone": string | null,
          "contact_email": string | null,
          "suggested_introduction": string
    }}
  ]
}}

"""

    import json
    resp = llm.invoke(prompt)
    try:
        summary_json = json.loads(resp.content)
        if not isinstance(summary_json, dict):
            raise ValueError("Expected dict")
    except Exception:
        # Fallback: simple JSON structure from the ranked list
        summary_json = {
            "overview": f"Top volunteer opportunities near {location} for {interests}.",
            "items": [
                {
                    "title": opp["title"],
                    "org": opp["org"],
                    "why_fit": "",
                    "time": opp["time"],
                    "location": opp.get("location", location),
                    "tags": opp.get("tags", []),
                    "url": opp["url"],
                    "phone": None,
                    "contact_email": None,
                    "suggested_introduction": "",
                }
                for opp in ranked[:5]
            ],
        }

    return {"summary": summary_json}

def build_volunteer_graph():
    graph = StateGraph(VolunteerState)

    # Add nodes
    graph.add_node("query", parse_user_query)
    graph.add_node("search", search_volunteer_opportunities)
    graph.add_node("rank", rank_opportunities)
    graph.add_node("summarize", summarize_results)

    # Entry point: start by parsing the query
    graph.set_entry_point("query")

    # Flow: query -> search -> rank -> summarize -> END
    graph.add_edge("query", "search")
    graph.add_edge("search", "rank")
    graph.add_edge("rank", "summarize")
    graph.add_edge("summarize", END)

    app = graph.compile()
    return app


if __name__ == "__main__":
    app = build_volunteer_graph()

    # Example run
    state_in = {
        "query": "I live in Seattle and want weekend animal volunteering, I like education too."
    }

    result = app.invoke(state_in)
    print("=== SUMMARY ===")
    print(result["summary"])
