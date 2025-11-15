# `test.py` Overview

This file defines a simple LangGraph workflow using a typed state and several nodes, and then runs it once when executed as a script.

## State definition

- Defines a `State` `TypedDict` with a single field:
  - `message: str` – the text message being processed through the graph.

## Nodes

- `step_uppercase(state: State)`
  - Reads `state["message"]` and returns a new state with the `message` uppercased.
- `classify(state)`
  - Looks at `state["message"]` (lowercased) and sets an `intent` key:
    - `"greeting"` if the message contains the word "hello".
    - `"other"` otherwise.
- `answer_hello`
  - Lambda node that returns `{"message": "Hi there!"}`.
- `answer_other`
  - Lambda node that returns `{"message": "I didn’t understand."}`.

## Graph construction

- Creates a `StateGraph(State)` instance named `graph`.
- Registers the following nodes:
  - `"uppercase"` → `step_uppercase`
  - `"classify"` → `classify`
  - `"answer_hello"` → hello response lambda
  - `"answer_other"` → fallback response lambda
- Sets the entry point to `"classify"`.
- Adds conditional edges out of `"classify"` based on `state["intent"]`:
  - `"greeting"` → `"answer_hello"`
  - `"other"` → `"answer_other"`
- Adds terminal edges:
  - `"answer_hello"` → `END`
  - `"answer_other"` → `END`
- Compiles the graph to an `app` object via `graph.compile()`.

## Script entry point

When you run `python3 test.py`, the `__main__` block:

1. Invokes the compiled `app` with an initial state: `{"message": "hello world"}`.
2. Prints the result to stdout as `App result: ...`.

This provides a minimal, runnable example of how to build and execute a LangGraph application using a typed state and simple branching logic.
