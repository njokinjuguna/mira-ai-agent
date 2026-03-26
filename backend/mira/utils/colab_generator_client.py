import os, base64, io, requests
from PIL import Image

def pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def b64_to_pil(b64: str) -> Image.Image:
    data = base64.b64decode(b64)
    return Image.open(io.BytesIO(data)).convert("RGB")

def generate_with_colab(prompt: str, ref_img: Image.Image, seed: int | None = None) -> Image.Image:
    base_url = os.getenv("COLAB_GENERATOR_URL", "").rstrip("/")
    if not base_url:
        raise ValueError("COLAB_GENERATOR_URL missing")

    payload = {
        "prompt": prompt,
        "reference_image_base64": pil_to_b64(ref_img),
        "seed": seed,
        "width": 768,
        "height": 768,
        "steps": 30,
        "guidance": 7.0,
        "controlnet_strength": 1.0,
    }

    r = requests.post(f"{base_url}/generate", json=payload, timeout=300)
    r.raise_for_status()
    out = r.json()
    return b64_to_pil(out["image_base64"])
