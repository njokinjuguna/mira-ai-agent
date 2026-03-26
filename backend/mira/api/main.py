from typing import Optional
from dotenv import load_dotenv
load_dotenv()
import io
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse
from mira.api.handlers.image_search import search_images
from mira.api.handlers.showroom_info import get_showroom_response
from mira.utils.drive_utils import load_drive_service, download_image
from mira.api.handlers.sketch_generation import handle_sketch_generation
from fastapi.responses import FileResponse
from mira.utils.logger import logger
from pydantic import BaseModel
from mira.agent.graph import build_graph
from mira.agent.memory import get_mem, set_mem




app = FastAPI()
graph = build_graph()

logger.info("🛠️ Mira backend booting...")

# ✅ CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Serve generated sketches as static files
app.mount("/generated", StaticFiles(directory="mira/data/generated"), name="generated")

class MiraRequest(BaseModel):
    query: str
    session_id: str
    lang: Optional[str] = None
class SearchRequest(BaseModel):
    query: str

class SelectReferenceRequest(BaseModel):
    session_id: str
    image_id: str

class ClearReferenceRequest(BaseModel):
    session_id: str

# ✅ Healthcheck & root
@app.get("/")
def read_root():
    return {"status": "Mira backend is running"}

@app.get("/healthcheck")
def healthcheck():
    return {"status": "ok"}


# ✅ Serve Google Drive Images using Service Account
@app.get("/image/{image_id:path}")
async def serve_drive_image(image_id: str):
    drive_service = load_drive_service()

    try:
        # ✅ normalize (fixes /image//generated/... and leading slashes)
        image_id = (image_id or "").lstrip("/")

        # ✅ If the request is for a generated sketch, serve it from disk
        if image_id.startswith("generated/"):
            filename = image_id.replace("generated/", "", 1)
            path = os.path.join("mira", "data", "generated", filename)

            if not os.path.exists(path):
                logger.error(f"[Generated Sketch Not Found] {path}")
                return {"error": "Generated sketch not found"}

            return FileResponse(path, media_type="image/png")

        # ✅ Otherwise treat it as a Google Drive image ID (existing behavior)
        img = download_image(drive_service, image_id)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/jpeg")

    except Exception as e:
        logger.error(f"[Image Retrieval Error] {e}")
        return {"error": "Immagine non trovata"}


@app.post("/session/clear-reference")
def clear_reference(req: ClearReferenceRequest):
    mem = get_mem(req.session_id)

    # ✅ Unlock
    mem["mode"] = "browse"
    mem["selected_sketch"] = None

    # ✅ Clear cached selection + paths
    mem.pop("selected_index", None)
    mem.pop("active_sketch_local_path", None)
    mem.pop("selected_sketch_local_path", None)

    # Optional: keep last_search_results so the gallery stays visible
    # mem.pop("last_search_results", None)

    set_mem(req.session_id, mem)
    return {"ok": True}

@app.post("/search")
def search(req: SearchRequest):
    query = (req.query or "").strip()
    if not query:
        return {"error": "Query cannot be empty."}

    result = search_images(query)
    return {"results": result}



@app.post("/sketch/select-reference")
def select_reference(req: SelectReferenceRequest):
    mem = get_mem(req.session_id)

    mem["selected_sketch"] = {"id": req.image_id}

    # ✅ MODE LOCK ON
    mem["mode"] = "sketch_generation"

    # Clear cached local path so _load_reference_image() loads the correct id
    mem.pop("selected_sketch_local_path", None)
    mem.pop("active_sketch_local_path", None)
    mem.pop("selected_index", None)

    # ✅ IMPORTANT: persist
    set_mem(req.session_id, mem)

    return {"ok": True, "selected_id": req.image_id}

# ✅ New endpoint: sketch generation
@app.post("/sketch/generate")
async def sketch_generate(payload: dict):
    query = (payload.get("query") or "").strip()
    session_id = (payload.get("session_id") or "").strip()
    lang = (payload.get("lang") or "").strip().lower()
    if lang not in {"en", "it"}:
        return {"type": "sketch_generation", "message": "Missing/invalid lang (use 'en' or 'it').", "lang": "en"}

    if not query:
        return {
            "type": "sketch_generation",
            "message": "Per favore, inserisci una richiesta con misure (es: 3.6m x 2.8m)." if lang != "en"
            else "Please provide a request with measurements (e.g., 3.6m x 2.8m).",
        }

    # OPTIONAL: Hook in your existing retrieval later
    resp = handle_sketch_generation(query=query, session_id=session_id, lang=lang)

    return resp

# ✅ Handlers for each type of intent
def handle_search_intent(query_en: str, lang: str, session_context: dict):
    results = search_images(query_en)

    # ✅ FIX 3: make this search the active gallery
    session_context["active_gallery_results"] = results
    session_context["active_gallery_intent"] = "search"

    # ✅ clear old selection + cached paths to prevent cross-topic leakage
    session_context["selected_sketch"] = None
    session_context.pop("active_sketch_local_path", None)
    session_context.pop("selected_sketch_local_path", None)

    session_context["last_intent"] = "search"
    session_context["last_search_results"] = results

    valid = [r for r in results if isinstance(r, dict) and r.get("id")]
    session_context["last_sketch_ids"] = [r["id"] for r in valid]
    session_context["last_sketch_captions"] = [r.get("caption", "") for r in valid]
    session_context["active_sketch"] = valid[0]["id"] if valid else None

    logger.debug(f"🧪 Raw image search results: {results}")


    if valid:
        results_clean = []
        for r in valid:
            caption = (r.get("caption") or "").strip()
            if not caption:
                caption = "No description available." if lang == "en" else "Nessuna descrizione disponibile."
            results_clean.append({**r, "caption": caption})
    else:
        # keep fallback dict if your search_images returns it
        results_clean = results

    header = (
        "Ecco alcune proposte che corrispondono alla tua descrizione.\nHere are some designs that match your request."
        if lang == "it"
        else "Here are some designs that match your request.\nEcco alcune proposte che corrispondono alla tua descrizione."
    )

    return {"type": "search", "results": results_clean, "header": header, "lang": lang}


def handle_showroom_intent(query_en: str, lang: str):
    answer = get_showroom_response(query_en)
    if lang == "it":
        answer_out = (
            f"{answer}\n\n"
            "If you want, I can also share this in English—tell me and I’ll summarize it."
        )
    else:
        # English first, then Italian
        # If your underlying showroom response is Italian, we still show it, but lead with English guidance.
        answer_out = (
            "Here are the showroom details:\n"
            f"{answer}\n\n"
            "Se vuoi, posso anche riassumerlo in italiano."
        )

    return {"type": "showroom", "answer": answer_out, "lang": lang}

def handle_cost_followup_intent(lang: str):
    default = {
        "it": "Per un preventivo dettagliato, ti invitiamo a consultare il nostro team di interior design.",
        "en": "For a detailed quote, we invite you to consult our interior design team."
    }
    return {"type": "cost", "answer": default.get(lang, default["it"]), "lang": lang}

def handle_unsupported_intent(lang: str):
    fallback = (
        "Mi dispiace, non ho capito la tua richiesta. Per favore, prova a dirlo in un altro modo.\n"
        "I'm sorry, I didn't understand your request. Please try to say it in another way."
    )
    return {"type": "unsupported", "answer": fallback, "lang": lang}


# ✅ Main Mira AI logic
@app.post("/mira")
def mira_router(req: MiraRequest):
    # LangGraph expects {query, session_id}
    out = graph.invoke({"query": req.query,"session_id": req.session_id, "lang": req.lang})

    # Standard response to the frontend
    return {
        "message": out.get("message", ""),
        "results": out.get("results", []),
        "type": out.get("type", out.get("intent", "mira")),
        "lang": out.get("lang", "en"),
    }


# ✅ Start the app
if __name__ == "__main__":
    uvicorn.run("mira.api.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
