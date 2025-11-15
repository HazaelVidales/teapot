from langgraph.graph import StateGraph, END
from typing import TypedDict

class State(TypedDict):
    message: str

def step_uppercase(state: State):
    return {"message": state["message"].upper()}


# Build the graph instance
graph = StateGraph(State)

def classify(state):
    msg = state["message"].lower()
    return {"intent": "greeting" if "hello" in msg else "other"}

graph.add_node("classify", classify)
graph.add_node("answer_hello", lambda s: {"message": "Hi there!"})
graph.add_node("answer_other", lambda s: {"message": "I didn’t understand."})

graph.set_entry_point("classify")

graph.add_conditional_edges(
    "classify",
    lambda s: s["intent"],
    {
        "greeting": "answer_hello",
        "other": "answer_other"
    }
)

graph.add_edge("answer_hello", END)
graph.add_edge("answer_other", END)

app = graph.compile()

# Simple test run
if __name__ == "__main__":
    result = app.invoke({"message": "hello world"})
    print("App result:", result)

