import pickle
import numpy as np
import torch
from mira.utils.model_loader import load_openclip

# Load image embeddings
with open("mira/data/embeddings_cache.pkl", "rb") as f:
    image_data = pickle.load(f)

# Load models
model, preprocess, tokenizer = load_openclip()



# ----------------------------
# Canonical room types (EN + IT + your flat folders)
# ----------------------------
# We use canonical names to avoid mismatches like:
# "living room" vs "sittingarea" vs "salotto"
CANONICAL = {
    "kitchen": "kitchen",
    "bathroom": "bathroom",
    "bedroom": "bedroom",
    "living_room": "living_room",
    "garden": "garden",
    "library": "library",
    "dining": "dining",
    "commercial": "commercial",
    "circulation": "circulation",
    "feature": "feature",
    "wardrobe": "bedroom",  # wardrobe is still effectively bedroom-related for retrieval
}

ROOM_KEYWORDS = {
    "kitchen": [
        "kitchen", "cucina", "angolo cottura", "fornelli", "lavello", "piano cottura",
        "fridge", "freezer", "oven", "stove", "sink", "isola", "island"
    ],
    "bathroom": [
        "bathroom", "bagno", "doccia", "vasca", "lavandino", "wc", "bidet",
        "shower", "bathtub", "toilet"
    ],
    "bedroom": [
        "camera da letto", "cameretta", "bedroom", "camera", "letto",
        "wardrobe", "armadio", "guardaroba", "comodino", "specchio",
        "dresser", "cassettiera", "cabina armadio", "walk-in"
    ],
    "living_room": [
        "living room", "living", "soggiorno", "salotto", "zona giorno",
        "divano", "tv", "lounge", "sofa", "sitting area", "sittingarea"
    ],
    "garden": [
        "garden", "giardino", "esterno", "outdoor", "patio", "terrazza", "balcone", "veranda"
    ],
    "library": [
        "library", "libreria", "biblioteca", "scaffale", "bookshelf", "bookcase", "studio"
    ],
    "dining": [
        "table", "tavolo", "zona pranzo", "pranzo", "dining", "sedie", "chairs"
    ],
    "commercial": [
        "shop", "negozio", "store", "boutique"
    ],
    "circulation": [
        "staircase", "scala", "scale"
    ],
    "feature": [
        "chimney", "camino", "caminetto"
    ],
}


def _normalize_text(s: str) -> str:
    return (s or "").lower().strip().replace("_", " ").replace("-", " ")


def detect_room_type(query: str):
    """
    Returns a CANONICAL room_type or None.
    We do a global longest-key-first match to avoid:
    'camera' matching before 'camera da letto'.
    """
    q = _normalize_text(query)
    if not q:
        return None

    # Build flat list of (keyword, room) and sort by keyword length desc
    pairs = []
    for room, keys in ROOM_KEYWORDS.items():
        for k in keys:
            pairs.append((_normalize_text(k), room))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)

    for k, room in pairs:
        if k and k in q:
            return room

    return None


def _category_matches(room_type: str, category: str) -> bool:
    """
    Fallback match when embeddings don't contain 'room_type'.
    This checks folder/category strings.
    """
    if not room_type:
        return True

    cat = _normalize_text(category)

    # direct canonical match
    if _normalize_text(room_type) in cat:
        return True

    # match any keyword for that canonical room
    for k in ROOM_KEYWORDS.get(room_type, []):
        if _normalize_text(k) in cat:
            return True

    # common plural folder names
    if room_type == "bedroom" and ("bedrooms" in cat or "camere" in cat):
        return True
    if room_type == "kitchen" and ("kitchens" in cat or "cucine" in cat):
        return True
    if room_type == "bathroom" and ("bathrooms" in cat or "bagni" in cat):
        return True

    # Your flat folders (explicit)
    if room_type == "living_room" and ("sittingarea" in cat or "sitting area" in cat):
        return True

    return False


def _img_room_type(img: dict) -> str:
    """
    Prefer the explicit 'room_type' field (best),
    otherwise fall back to category.
    """
    rt = img.get("room_type")
    if rt:
        return _normalize_text(rt)

    # fallback to category if room_type doesn't exist yet
    return _normalize_text(img.get("category", ""))


def clean_caption(caption: str, room_hint: str = None):
    """
    Keep caption cleaning conservative (no meaning changes).
    Only remove vague starts.
    """
    if not caption:
        return ""

    c = caption.strip()
    vague_starts = ("a drawing of", "a sketch of", "an illustration of", "drawing of", "sketch of")
    c_low = c.lower()

    if c_low.startswith(vague_starts):
        tail = c.split("of", 1)[-1].strip()
        if room_hint:
            return f"{room_hint} sketch: {tail}"
        return tail

    return c


def search_images(query, top_k=5, threshold=0.25):
    """
    Pass 1: strict room lock (if room detected) + threshold
    Pass 2: relaxed threshold BUT keep room lock if room detected
    """
    q0 = (query or "").strip()
    room_hint = detect_room_type(q0)  # canonical room type
    room_hint_label = room_hint.replace("_", " ") if room_hint else None

    def _search(q, lock_room=True, thr=threshold):
        q_clean = (q or "").strip()
        if not q_clean:
            return []

        with torch.no_grad():
            tokens = tokenizer([q_clean])
            text_features = model.encode_text(tokens).cpu().numpy()[0]

        detected = detect_room_type(q_clean)
        room_type = detected if lock_room else None

        scores = []
        for img in image_data:
            # ✅ Best: use explicit room_type if present
            if room_type:
                img_rt = _img_room_type(img)
                # if we have 'room_type', this is strict equality
                if img.get("room_type"):
                    if img_rt != _normalize_text(room_type):
                        continue
                else:
                    # fallback to category matching if room_type not stored yet
                    if not _category_matches(room_type, img.get("category", "")):
                        continue

            img_emb = img.get("embedding")
            if img_emb is None:
                continue

            denom = (np.linalg.norm(text_features) * np.linalg.norm(img_emb))
            if denom == 0:
                continue

            score = float(np.dot(text_features, img_emb) / denom)
            scores.append((img, score))

        # Pull more first, then threshold filter
        pre_top = sorted(scores, key=lambda x: x[1], reverse=True)[: max(top_k * 3, 15)]

        filtered = [
            {
                "id": match.get("id"),
                "best_match": match.get("name"),
                "caption": clean_caption(match.get("caption", ""), room_hint_label),
                "image_url": f"/image/{match.get('id')}",
                "score": float(score),
                "category": match.get("category", ""),
                "room_type": match.get("room_type", None),
            }
            for match, score in pre_top
            if score >= thr and match.get("id")
        ]

        return filtered[:top_k]

    # ✅ Pass 1: strict lock if we detected a room
    results = _search(q0, lock_room=True, thr=threshold)
    if results:
        return results

    # ✅ Pass 2: relax threshold, but DO NOT unlock room if detected
    relaxed_thr = max(0.20, threshold - 0.05)

    if room_hint:
        # keep room lock
        results = _search(q0, lock_room=True, thr=relaxed_thr)
    else:
        # only unlock if no room detected
        results = _search(q0, lock_room=False, thr=relaxed_thr)

    if results:
        return results

    return [{"message": "❌ Nessuna buona corrispondenza trovata. Prova a riformulare la descrizione."}]
