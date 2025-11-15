from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

class VolunteerState(TypedDict, total=False):
    location: str
    interests: List[str]
    raw_results: List[Dict]
    ranked_results: List[Dict]
    summary: str

def search_volunteer_opportunities(state: VolunteerState) -> VolunteerState:
    location = state["location"]
    interests = state.get("interests", [])

    # TODO: replace this with real API calls
    fake_db = [
        {
            "title": "Food Bank Helper",
            "org": "City Food Bank",
            "location": location,
            "tags": ["food", "community", "logistics"],
            "time": "Saturdays 9–12",
            "url": "https://example.org/foodbank"
        },
        {
            "title": "Dog Walker Volunteer",
            "org": "Happy Paws Shelter",
            "location": location,
            "tags": ["animals", "outdoors"],
            "time": "Weekdays evenings",
            "url": "https://example.org/dogs"
        },
        {
            "title": "STEM Tutor",
            "org": "Local Youth Center",
            "location": location,
            "tags": ["education", "kids", "math"],
            "time": "Two evenings per week",
            "url": "https://example.org/stem"
        },
    ]

    # Simple filter by interests if provided
    if interests:
        filtered = []
        for opp in fake_db:
            if any(interest.lower() in " ".join(opp["tags"]).lower() for interest in interests):
                filtered.append(opp)
    else:
        filtered = fake_db

    return {"raw_results": filtered}

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
        text = f"No volunteer opportunities found near {location} for interests {interests}."
        return {"summary": text}

    # Build a compact listing string
    lines = []
    for i, opp in enumerate(ranked[:5], start=1):
        lines.append(
            f"{i}. {opp['title']} at {opp['org']} "
            f"({opp['time']}) – tags: {', '.join(opp['tags'])} – {opp['url']}"
        )
    listing = "\n".join(lines)

    prompt = f"""
You are helping someone find volunteer opportunities.

Location: {location}
Interests: {', '.join(interests) if interests else 'not specified'}

Here are the options:

{listing}

Write:
- A short friendly overview
- Then a bullet list of 3–5 best options with:
  - title
  - org
  - why it fits their interests
  - practical details (time, location style if possible)
"""

    resp = llm.invoke(prompt)
    return {"summary": resp.content}

def build_volunteer_graph():
    graph = StateGraph(VolunteerState)

    # Add nodes
    graph.add_node("search", search_volunteer_opportunities)
    graph.add_node("rank", rank_opportunities)
    graph.add_node("summarize", summarize_results)

    # Entry point: start by searching
    graph.set_entry_point("search")

    # Linear flow: search -> rank -> summarize -> END
    graph.add_edge("search", "rank")
    graph.add_edge("rank", "summarize")
    graph.add_edge("summarize", END)

    app = graph.compile()
    return app


if __name__ == "__main__":
    app = build_volunteer_graph()

    # Example run
    state_in = {
        "location": "Seattle, WA",
        "interests": ["animals", "education"]
    }

    result = app.invoke(state_in)
    print("=== SUMMARY ===")
    print(result["summary"])
