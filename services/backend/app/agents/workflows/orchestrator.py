from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.router import classify_many
from app.core.config import get_settings


class FlowState(TypedDict, total=False):
    text: str
    context: str
    proposals: list
    refine: bool


def build_graph(checkpointer=None):
    graph = StateGraph(FlowState)
    graph.add_node(
        "coordinator",
        lambda state: {
            "proposals": classify_many(state["text"], state["context"]),
            "refine": get_settings().ai_mode == "groq",
        },
    )
    graph.add_edge(START, "coordinator")
    graph.add_edge("coordinator", END)
    return graph.compile(checkpointer=checkpointer)


workflow = build_graph()
