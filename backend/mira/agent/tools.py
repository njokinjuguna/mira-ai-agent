import os
import re
from mira.utils.drive_utils import load_drive_service, download_image_to_path
from typing import Dict, Any, List,Optional
from langchain_core.tools import tool

from mira.agent.memory import get_mem, set_mem
from mira.utils.designer_tone import designer_message

from mira.api.handlers.image_search import search_images
from mira.api.handlers.showroom_info import get_showroom_response
from mira.api.handlers.sketch_generation import handle_sketch_generation


def rewrite_query_for_search(q: str) -> str:
    """Light rewrite to improve recall for multi-word queries."""
    q2 = (q or "").lower().strip()

    # Expand common interior terms
    q2 = q2.replace("wardrobe", "wardrobe closet")
    q2 = q2.replace("closet", "wardrobe closet")
    q2 = q2.replace("dresser", "dresser cabinet")

    # Remove filler words (keep this conservative)
    fillers = {"sketch", "drawing", "please", "show me", "i want"}
    for f in fillers:
        q2 = q2.replace(f, " ")

    q2 = " ".join(q2.split())
    return q2


def _is_fallback_message(raw: Any) -> bool:
    """Detect your search_images fallback format: [{'message': '...'}]."""
    return (
        isinstance(raw, list)
        and len(raw) > 0
        and isinstance(raw[0], dict)
        and "message" in raw[0]
        and len(raw[0].keys()) == 1
    )

@tool
def search_tool(session_id: str, query: str, lang: str = "en", top_k: int = 3) -> Dict[str, Any]:
    """Search for relevant sketches/images and store indexed results in session memory."""
    mem = get_mem(session_id)

    q_clean = (query or "").strip()

    # ✅ Keep language stable: if query is short, reuse previous language
    # ✅ language comes from graph; keep memory in sync
    lang = (lang or mem.get("lang") or "en").strip().lower()
    if lang not in {"en", "it"}:
        lang = "en"
    mem["lang"] = lang

    # ✅ Auto-select if user references a specific design/drawing number
    m = re.search(r"\b(design|drawing|sketch|disegno)\s*(\d+)\b", q_clean.lower())
    if m:
        idx = int(m.group(2))
        if mem.get("last_search_results"):
            # This will also trigger local caching in select_tool
            _ = select_tool.invoke({"session_id": session_id, "index": idx})
            mem = get_mem(session_id)  # refresh after select


    # ✅ Rewrite query first (but keep original as fallback)
    query2 = rewrite_query_for_search(q_clean)

    # Try rewritten query first (usually better for multi-word queries)
    raw = search_images(query=query2, top_k=top_k)

    # If rewrite hurt results, fall back to original query
    if _is_fallback_message(raw) and query2 != q_clean:
        raw = search_images(query=q_clean, top_k=top_k)

    # ✅ If still fallback, clear memory + return message
    if _is_fallback_message(raw):
        msg = raw[0]["message"]

        mem["lang"] = lang
        mem["last_query"] = q_clean
        mem["last_search_results"] = []
        mem["last_sketch_ids"] = []
        mem.pop("active_sketch_id", None)
        mem.pop("selected_sketch", None)
        mem.pop("selected_index", None)

        # ✅ new search = browsing mode (unlock generation lock)
        mem["mode"] = "browse"
        mem["selected_sketch"] = None
        mem.pop("selected_index", None)
        mem.pop("active_sketch_local_path", None)
        mem.pop("selected_sketch_local_path", None)

        set_mem(session_id, mem)
        return {"message": msg, "results": [], "type": "search", "lang": lang}

    # ✅ Index results + standardize image_url
    indexed: List[Dict[str, Any]] = []
    for i, r in enumerate(raw, start=1):
        r2 = dict(r)
        r2["index"] = i

        # Ensure image_url always points to backend image route
        if "id" in r2:
            r2["image_url"] = f"/image/{r2['id']}"

        indexed.append(r2)

    # ✅ Save to memory for "drawing 2" + modifications
    mem["lang"] = lang
    mem["last_query"] = q_clean
    mem["last_search_results"] = indexed
    mem["last_sketch_ids"] = [r["id"] for r in indexed if "id" in r]

    # ✅ Successful new search = browsing mode (unlock generation lock)
    mem["mode"] = "browse"
    mem["selected_sketch"] = None
    mem.pop("selected_index", None)
    mem.pop("active_sketch_local_path", None)
    mem.pop("selected_sketch_local_path", None)

    set_mem(session_id, mem)


    msg = designer_message(intent="search", lang=lang, query=q_clean, results=indexed)
    return {"message": msg, "results": indexed, "type": "search", "lang": lang}


@tool
def select_tool(session_id: str, index: int) -> Dict[str, Any]:
    """Select a sketch by index (e.g. drawing 2) and mark it as active."""
    mem = get_mem(session_id)
    lang = mem.get("lang", "en")
    last = mem.get("last_search_results", [])
    q = mem.get("last_query", "")

    chosen = next((x for x in last if x.get("index") == index), None)
    if not chosen:
        msg = designer_message(intent="select_not_found", lang=lang, query=q, results=[])
        return {"message": msg, "results": [], "type": "select", "lang": lang}

    mem["selected_index"] = index
    mem["selected_sketch"] = chosen
    mem["active_sketch_id"] = chosen.get("id")

    # ✅ NEW: cache the selected sketch locally so sketch_generation won't hit Drive again
    try:
        ref_id = chosen.get("id")
        if ref_id:
            cache_dir = os.path.join("mira", "data", "ref_cache")
            local_path = os.path.join(cache_dir, f"{ref_id}.png")

            # only download if not already cached
            if not os.path.exists(local_path):
                drive = load_drive_service()
                download_image_to_path(drive, ref_id, local_path)

            mem["active_sketch_local_path"] = local_path
            mem["selected_sketch_local_path"] = local_path
    except Exception as e:
        # Don't fail selection if caching fails; just log later if you want
        mem["active_sketch_local_path"] = None
        mem["selected_sketch_local_path"] = None

    set_mem(session_id, mem)

    msg = designer_message(intent="select", lang=lang, query=q, results=[chosen])
    return {"message": msg, "results": [chosen], "type": "select", "lang": lang}





@tool
def cost_tool(session_id: str, query: str) -> Dict[str, Any]:
    """Handle cost or price follow-up questions for the selected sketch."""
    mem = get_mem(session_id)
    lang = mem.get("lang", "en")
    q = mem.get("last_query", "") or (query or "")

    sel = mem.get("selected_sketch") or (mem.get("last_search_results") or [None])[0]
    if not sel:
        msg = designer_message(intent="cost_no_context", lang=lang, query=q, results=[])
        return {"message": msg, "results": [], "type": "follow_up_cost", "lang": lang}

    msg = designer_message(intent="follow_up_cost", lang=lang, query=q, results=[sel])
    return {"message": msg, "results": [sel], "type": "follow_up_cost", "lang": lang}


@tool
def showroom_tool(query: str, lang: str = "en") -> Dict[str, Any]:
    """Answer showroom-related questions such as location, hours, or contacts."""
    lang = (lang or "en").strip().lower()
    if lang not in {"en", "it"}:
        lang = "en"

    # NOTE: adjust get_showroom_response signature depending on your handler
    # If the get_showroom_response doesn't accept language, remove the argument.
    try:
        text = get_showroom_response(query=query, language=lang)
    except TypeError:
        text = get_showroom_response(query)

    return {"message": text, "results": [], "type": "showroom", "lang": lang}


@tool
def sketch_tool(session_id: str, query: str, lang: str = "en") -> Dict[str, Any]:

    """
    Turbo sketch generation (NO REFERENCES).
    User prompt -> Colab Turbo -> generated image returned.
    """
    mem = get_mem(session_id)

    q_clean = (query or "").strip()

    # Keep language stable
    lang = (lang or mem.get("lang") or "en").strip().lower()
    if lang not in {"en", "it"}:
        lang = "en"
    mem["lang"] = lang
    # Since we're NOT using references anymore, remove any old locks/selection
    mem["mode"] = "browse"
    mem["selected_sketch"] = None
    mem.pop("selected_index", None)
    mem.pop("active_sketch_id", None)
    mem.pop("active_sketch_local_path", None)
    mem.pop("selected_sketch_local_path", None)

    set_mem(session_id, mem)

    out = handle_sketch_generation(query=q_clean, session_id=session_id, lang=lang)

    img_url = out.get("image_url", "")
    msg = out.get("message", "")

    if not img_url:
        return {
            "type": "sketch_generation",
            "message": msg or ("Generation failed. Please try again." if lang == "en" else "Generazione fallita. Riprova."),
            "results": [],
            "lang": lang,
        }

    results = [{
        "image_url": img_url,
        "caption": msg,
        "best_match": "Generated sketch (Turbo)",
        "score": 1.0,
        "id": img_url.split("/")[-1].replace(".png", ""),
    }]

    mem["last_generated"] = results[0]
    set_mem(session_id, mem)

    return {"type": "sketch_generation", "message": msg, "results": results, "lang": lang}

