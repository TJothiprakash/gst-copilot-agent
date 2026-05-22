from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import GSTState
from agent.nodes.ingest import ingest_node
from agent.nodes.classify import classify_node
from agent.nodes.validate import validate_node
from agent.nodes.compute import compute_node
from agent.nodes.draft_gstr import draft_gstr_node
from agent.nodes.explain import explain_node


# ── Routing logic ─────────────────────────────────────────────────────────────
def route_after_validate(state: GSTState) -> str:
    if state.get("needs_human_review"):
        return "human_review"
    return "compute"


def route_after_human_review(state: GSTState) -> str:
    if state.get("human_confirmed"):
        return "compute"
    return END


# ── Human review node (pause point) ──────────────────────────────────────────
async def human_review_node(state: GSTState) -> GSTState:
    print(f"[human_review] Pausing for human review")
    print(f"[human_review] Errors: {state.get('errors')}")
    print(f"[human_review] Warnings: {state.get('warnings')}")
    return {
        **state,
        "current_node": "human_review",
        "human_confirmed": False,
    }


# ── Build the graph ───────────────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(GSTState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    graph.add_node("ingest", ingest_node)
    graph.add_node("classify", classify_node)
    graph.add_node("validate", validate_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("compute", compute_node)
    graph.add_node("draft_gstr", draft_gstr_node)
    graph.add_node("explain", explain_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("ingest")

    # ── Edges ─────────────────────────────────────────────────────────────────
    graph.add_edge("ingest", "classify")
    graph.add_edge("classify", "validate")

    # ── Conditional routing after validate ────────────────────────────────────
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "human_review": "human_review",
            "compute": "compute",
        }
    )

    # ── Conditional routing after human review ────────────────────────────────
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "compute": "compute",
            END: END,
        }
    )

    # ── Linear flow after compute ─────────────────────────────────────────────
    graph.add_edge("compute", "draft_gstr")
    graph.add_edge("draft_gstr", "explain")
    graph.add_edge("explain", END)

    # ── Compile with memory checkpointer ──────────────────────────────────────
    memory = MemorySaver()
    return graph.compile(
        checkpointer=memory,
        interrupt_before=["human_review"],
    )


# ── Singleton graph instance ──────────────────────────────────────────────────
gst_graph = build_graph()