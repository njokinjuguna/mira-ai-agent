import os
import json
from typing import Literal

import joblib
import re

from mira.utils.query_preprocessor import extract_keywords
from mira.utils.logger import logger
from mira.utils.intent_logger import log_intent_entry

# ✅ Load model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "model", "intent_classifier.pkl")
classifier = joblib.load(MODEL_PATH)

# ✅ Load keyword fallback config
KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), "..", "utils", "intent_keywords.json")


def load_intent_keywords():
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


keywords_config = load_intent_keywords()


def _looks_like_sketch_generation(q: str) -> bool:
    ql = (q or "").lower().strip()

    # ✅ Must contain explicit generate/create signals
    gen_signals = [
        "generate", "create", "make", "produce", "draw", "sketch",
        "genera", "crea", "fammi", "disegna", "schizzo", "disegno", "progetto",
        "new sketch", "new design", "nuovo schizzo", "nuovo disegno", "nuovo progetto",
    ]
    has_gen = any(s in ql for s in gen_signals)

    # ✅ Must mention a room / context
    room_hints = [
        "kitchen", "bathroom", "bedroom", "living", "garden", "office",
        "cucina", "bagno", "camera", "salotto", "giardino", "ufficio",
    ]
    has_room = any(r in ql for r in room_hints)

    # ✅ Constraints (optional now)
    has_dims = bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:m|cm|mm)?\s*[x×]\s*\d+(?:[.,]\d+)?\s*(?:m|cm|mm)?\b", ql))
    has_sizes = bool(re.search(r"\b\d+\s*(?:cm|mm|m)\b", ql))
    has_layout = any(k in ql for k in ["l shape", "l-shape", "u shape", "u-shape", "galley", "straight", "lineare", "una parete"])

    # ✅ IMPORTANT CHANGE:
    # If user says "generate/create" + mentions a room, treat it as sketch_generation
    # even without dimensions/reference (because you no longer require references).
    if has_gen and has_room:
        return True

    # Still allow "drawing 1" style phrasing to count as generation too
    has_ref = bool(re.search(r"\b(drawing|design|sketch|disegno)\s*\d+\b", ql))
    if has_gen and has_ref:
        return True

    # If you want to keep stricter logic for non-room prompts, use constraints:
    return bool(has_gen and (has_dims or has_sizes or has_layout))

def _looks_like_smalltalk(q: str) -> bool:
    ql = (q or "").lower().strip()

    patterns = [
        "hello", "hi", "hey", "good morning", "good evening",
        "how are you", "how old are you", "who are you", "what are you",
        "ciao", "salve", "buongiorno", "buonasera",
        "come stai", "come va", "quanti anni hai", "chi sei",
    ]
    return any(p in ql for p in patterns)


def detect_intent(query: str,lang:Literal["en","it"]) -> str:
    logger.info("\n========================= INTENT CLASSIFIER =========================")
    logger.info(f"[Intent] Raw Query: {query}")

    if not query or not isinstance(query, str):
        logger.warning("[Intent] Received empty or invalid query.")
        return "unsupported"

    # ✅ 0) Rule override for sketch generation (first priority)
    try:
        if _looks_like_sketch_generation(query):
            logger.info("[Rule Override] → sketch_generation")
            log_intent_entry(query, "sketch_generation", source="rule")
            return "sketch_generation"
    except Exception as e:
        logger.warning(f"[Sketch Rule Error] {e}")
    # 1) Hard rule: smalltalk -> unsupported
    try:
        if _looks_like_smalltalk(query):
            logger.info("[Rule Override] → unsupported (smalltalk)")
            log_intent_entry(query, "unsupported", source="rule_smalltalk")
            return "unsupported"
    except Exception as e:
        logger.warning(f"[Smalltalk Rule Error] {e}")


    # Step 2: classifier
    CONFIDENCE_THRESHOLD = 0.35

    try:
        predicted = classifier.predict([query])[0]
        proba = classifier.predict_proba([query])[0]
        confidence = max(proba)
        logger.info(f"[Classifier Prediction] → {predicted} (Confidence: {confidence:.2f})")

        if confidence >= CONFIDENCE_THRESHOLD:
            log_intent_entry(query, predicted, source=f"classifier ({confidence:.2f})")
            return predicted
        else:
            logger.info(f"⛔ Confidence too low ({confidence:.2f}). Fallback triggered.")
            raise ValueError("Low confidence")

    except Exception as e:
        logger.warning(f"[Classifier Error] Falling back to keyword logic: {e}")

    # Step 3: Extract keywords (fallback)
    keywords = extract_keywords(query)
    q = " ".join(keywords)
    logger.info(f"🔍 [Fallback] Extracted Keywords: {keywords}")


    # Step 4: Rule-based multilingual keyword matching
    for intent, langs in keywords_config.items():
        for kw in langs.get(lang, []):
            if kw in q:
                logger.info(f"✅ [Fallback Keyword Match] → {intent}")
                log_intent_entry(query, intent, source="fallback")
                return intent

    logger.info("❌ No keyword match found in fallback keywords")
    logger.info("🔚 [Fallback] → unsupported")
    log_intent_entry(query, "unsupported", source="fallback")
    return "unsupported"
