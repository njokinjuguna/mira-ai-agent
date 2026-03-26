import re
from langgraph.graph import StateGraph, END
from mira.agent.state import MiraState
from mira.agent.memory import get_mem, set_mem
from mira.agent.tools import (
    search_tool,
    select_tool,
    cost_tool,
    showroom_tool,
    sketch_tool,
)
# ✅ IMPORTANT: my real classifier+rules router
from mira.api.router import detect_intent as detect_intent_router
from mira.utils.language_utils import detect_language


def parse_drawing_ref(text: str):
    m = re.search(r"\b(design|drawing|draw|sketch|disegno | progetto | progetti )\s*(\d+)\b", (text or "").lower())
    return int(m.group(2)) if m else None


def node_prepare(state: MiraState) -> MiraState:
    q = (state.get("query") or "").strip()

    # 1) Detect language from the query (source of truth)
    detected = detect_language(q)  # 'en' | 'it' | 'unsupported'

    if detected not in {"en", "it"}:
        # 2) Reject unsupported languages immediately
        state["lang"] = "en"  # safe default for meta; message is bilingual
        state["intent"] = "unsupported"
        state["type"] = "unsupported"
        state["results"] = []
        state["message"] = (
            "Sorry — I currently support only English and Italian.\n"
            "Mi dispiace — al momento supporto solo inglese e italiano."
        )
        return state

    # 3) Keep detected language in state (do not use incoming state['lang'])
    state["lang"] = detected

    mem = get_mem(state["session_id"])

    # 4) Intent detection using detected language
    intent = detect_intent_router(q, state["lang"])

    # 5) MODE LOCK (language-agnostic)
    locked = mem.get("mode") == "sketch_generation" and (mem.get("selected_sketch") or {}).get("id")

    if locked:
        if intent in {"showroom", "follow_up_cost"}:
            state["intent"] = intent
        else:
            state["intent"] = "sketch_generation"
    else:
        state["intent"] = intent

    state["last_search_results"] = mem.get("last_search_results", [])
    state["selected_sketch"] = mem.get("selected_sketch")
    return state




def node_search(state: MiraState) -> MiraState:
    out = search_tool.invoke({
        "session_id": state["session_id"],
        "query": state["query"],
        "lang": state["lang"],
        "top_k": 3
    })
    state["message"] = out.get("message", "")
    state["results"] = out.get("results", [])
    state["type"] = out.get("type", "search")
    if "lang" in out:
        state["lang"] = out["lang"]
    return state


def node_select(state: MiraState) -> MiraState:
    idx = parse_drawing_ref(state["query"]) or 1
    out = select_tool.invoke({"session_id": state["session_id"], "index": idx})
    state["message"] = out.get("message", "")
    state["results"] = out.get("results", [])
    state["type"] = out.get("type", "select")
    if "lang" in out:
        state["lang"] = out["lang"]
    return state


def node_cost(state: MiraState) -> MiraState:
    out = cost_tool.invoke({"session_id": state["session_id"], "query": state["query"]})
    state["message"] = out.get("message", "")
    state["results"] = out.get("results", [])
    state["type"] = out.get("type", "follow_up_cost")
    if "lang" in out:
        state["lang"] = out["lang"]
    return state


def node_showroom(state: MiraState) -> MiraState:
    out = showroom_tool.invoke({"query": state["query"], "lang": state["lang"]})
    state["message"] = out.get("message", "")
    state["results"] = out.get("results", [])
    state["type"] = out.get("type", "showroom")
    if "lang" in out:
        state["lang"] = out["lang"]
    return state


def node_sketch_generation(state: MiraState) -> MiraState:
    payload = {
        "session_id": state["session_id"],
        "query": state["query"],
        "lang": state["lang"],
    }

    out = sketch_tool.invoke(payload)

    state["message"] = out.get("message", "")
    state["results"] = out.get("results", [])
    state["type"] = out.get("type", "sketch_generation")
    if "lang" in out:
        state["lang"] = out["lang"]
    return state


def node_unsupported(state: MiraState) -> MiraState:
    lang = state.get("lang", "en")
    state["type"] = "unsupported"
    state["results"] = []

    # If prepare already set a message (unsupported language), keep it
    if state.get("message"):
        return state

    if lang == "it":
        state["message"] = (
            "Mi dispiace, non ho capito la tua richiesta.\n"
            "Posso aiutarti con: ricerca disegni, info showroom, preventivi, oppure generare uno schizzo."
        )
    else:
        state["message"] = (
            "I'm sorry, I didn't understand your request.\n"
            "I can help with: design search, showroom info, pricing, or generating a sketch."
        )
    return state



def route(state: MiraState) -> str:
    allowed = {"search", "select", "follow_up_cost", "showroom", "sketch_generation","unsupported"}
    intent = state.get("intent", "unsupported")
    return intent if intent in allowed else "unsupported"


def build_graph():
    g = StateGraph(MiraState)
    g.add_node("prepare", node_prepare)
    g.add_node("search", node_search)
    g.add_node("select", node_select)
    g.add_node("follow_up_cost", node_cost)
    g.add_node("showroom", node_showroom)
    g.add_node("sketch_generation", node_sketch_generation)
    g.add_node("unsupported", node_unsupported)
    g.set_entry_point("prepare")

    g.add_conditional_edges(
        "prepare",
        route,
        {
            "search": "search",
            "select": "select",
            "follow_up_cost": "follow_up_cost",
            "showroom": "showroom",
            "sketch_generation": "sketch_generation",
            "unsupported": "unsupported",

        },
    )

    g.add_edge("search", END)
    g.add_edge("select", END)
    g.add_edge("follow_up_cost", END)
    g.add_edge("showroom", END)
    g.add_edge("sketch_generation", END)
    g.add_edge("unsupported", END)

    return g.compile()
