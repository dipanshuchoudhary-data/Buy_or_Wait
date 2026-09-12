from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from src.data.repositories import Repository
from src.orchestration.nodes import (
    build_decision_node,
    build_financial_state_node,
    extract_image_amounts,
    extract_message_facts_node,
    generate_and_rank_plans,
    load_context,
    reconcile_evidence,
    run_forecast,
    validate_request,
)
from src.orchestration.state import BuyWaitState


def build_graph(repository: Repository):
    graph = StateGraph(BuyWaitState)
    graph.add_node("validate_request", validate_request)
    graph.add_node("load_context", partial(load_context, repository=repository))
    graph.add_node("extract_image_amounts", partial(extract_image_amounts, repository=repository))
    graph.add_node("extract_message_facts", extract_message_facts_node)
    graph.add_node("reconcile_evidence", reconcile_evidence)
    graph.add_node(
        "build_financial_state",
        partial(build_financial_state_node, repository=repository),
    )
    graph.add_node("run_forecast", run_forecast)
    graph.add_node("generate_plans", generate_and_rank_plans)
    graph.add_node("build_decision", build_decision_node)

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "load_context")
    graph.add_edge("load_context", "extract_image_amounts")
    graph.add_edge("extract_image_amounts", "extract_message_facts")
    graph.add_edge("extract_message_facts", "reconcile_evidence")
    graph.add_edge("reconcile_evidence", "build_financial_state")
    graph.add_edge("build_financial_state", "run_forecast")
    graph.add_edge("run_forecast", "generate_plans")
    graph.add_edge("generate_plans", "build_decision")
    graph.add_edge("build_decision", END)
    return graph.compile()
