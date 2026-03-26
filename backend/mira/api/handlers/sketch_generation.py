# mira/api/handlers/sketch_generation.py
import os, uuid, base64, io, time
import httpx
from PIL import Image
from mira.utils.logger import logger

DEFAULT_NEG = "photo, realistic, blurry, low quality, messy lines, extra objects, text, watermark, logo"

def _call_colab_turbo(colab_url: str, payload: dict) -> dict:
    """
    Calls Colab Turbo endpoint: POST {COLAB_URL}/generate
    - Uses HTTPS
    - Follows redirects (ngrok 307)
    - Retries on flaky SSL/network issues
    """
    colab_url = (colab_url or "").rstrip("/")
    url = f"{colab_url}/generate"

    timeout = httpx.Timeout(600.0, connect=30.0)
    tries = 3
    last_err = None

    for attempt in range(1, tries + 1):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, http2=False) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            last_err = e
            logger.error(f"[COLAB CALL ERROR] attempt={attempt}/{tries} err={str(e)[:200]}")
            time.sleep(1.0 * attempt)

    raise RuntimeError(f"Colab unreachable after retries: {str(last_err)[:200]}")

def handle_sketch_generation(query: str, session_id: str, lang: str = "it"):
    """
    Turbo: prompt -> image (no reference)
    Saves result into mira/data/generated and returns /generated/<filename>
    """
    COLAB_URL = (os.getenv("COLAB_GENERATOR_URL") or "").rstrip("/")
    if not COLAB_URL:
        return {"type": "sketch_generation", "message": "COLAB_GENERATOR_URL missing in .env", "image_url": ""}

    prompt = (query or "").strip()
    if not prompt:
        return {"type": "sketch_generation", "message": "Empty prompt.", "image_url": ""}

    # Turbo payload (matches your Option A style)
    payload = {
        "prompt": prompt,
        "negative_prompt": DEFAULT_NEG,
        "width": 768,
        "height": 768,
        "steps": 4,
        "guidance": 0.0,
        "seed": None,
    }

    logger.info(f"🧪 Turbo prompt preview: {prompt[:160]}")
    logger.info(f"🎨 Calling Turbo Colab: {COLAB_URL}/generate")

    try:
        data = _call_colab_turbo(COLAB_URL, payload)
    except Exception as e:
        logger.error(f"[COLAB CALL FAILED] {e}")
        return {
            "type": "sketch_generation",
            "message": "Colab connection failed. Please retry (ngrok can be unstable).",
            "image_url": "",
            "error": str(e)[:180],
        }

    out_dir = os.path.join("mira", "data", "generated")
    os.makedirs(out_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.png"
    out_path = os.path.join(out_dir, filename)

    img_b64 = data.get("image_base64")
    if not img_b64:
        return {"type": "sketch_generation", "message": "Colab returned no image.", "image_url": ""}

    img_bytes = base64.b64decode(img_b64)
    with open(out_path, "wb") as f:
        f.write(img_bytes)

    msg = (
        "Ecco un nuovo concept generato dal prompt (Turbo)."
        if lang == "it"
        else "Here is a new concept generated from your prompt (Turbo)."
    )

    return {
        "type": "sketch_generation",
        "message": msg,
        "image_url": f"/generated/{filename}",
        "seed": data.get("seed"),
    }
