# mira/utils/language_utils.py
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0

SUPPORTED = {"en", "it"}

def detect_language(text: str) -> str:
    """
    Returns 'en' or 'it' only.
    Returns 'unsupported' for any other language or detection failure.
    """
    try:
        lang = detect((text or "").strip())
        return lang if lang in SUPPORTED else "unsupported"
    except LangDetectException:
        return "unsupported"
