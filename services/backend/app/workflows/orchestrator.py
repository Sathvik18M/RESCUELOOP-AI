from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.router import classify, refine_specialist


class FlowState(TypedDict, total=False):
    text: str
    context: str
    proposal: dict
    specialist: str


def build_graph(checkpointer=None):
    graph = StateGraph(FlowState)
    graph.add_node("conversation", lambda state: {"proposal": classify(state["text"], state["context"])})
    graph.add_node("shopping", lambda state: refine_specialist(state, "shopping"))
    graph.add_node("resolution", lambda state: refine_specialist(state, "resolution"))
    graph.add_node("general", lambda state: {"specialist": "conversation"})
    graph.add_edge(START, "conversation")

    def route(state):
        intent = state["proposal"]["intent"]
        if intent in {"catalog", "customization", "checkout"}:
            return "shopping"
        if intent in {
            "pickup",
            "redelivery",
            "refund",
            "return",
            "replacement",
            "cancellation",
            "warranty",
            "complaint",
        }:
            return "resolution"
        return "general"

    graph.add_conditional_edges("conversation", route)
    for node in ("shopping", "resolution", "general"):
        graph.add_edge(node, END)
    return graph.compile(checkpointer=checkpointer)


workflow = build_graph()
