from transformers import pipeline
from mira.utils.logger import logger

# Define the possible intents
INTENT_LABELS = ["search", "showroom", "follow_up_cost"]

# Load zero-shot classifier from Hugging Face (facebook/bart-large-mnli)
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def classify_intent_zero_shot(query: str) -> str:
    """
    Classifies a user query into one of:
    - search
    - showroom
    - follow_up_cost

    Uses Hugging Face's zero-shot model (BART).
    """
    logger.info("🧠 [ZIC] Classifying with Hugging Face Zero-Shot Classifier")
    logger.info(f"📩 [ZIC] Query: {query}")

    try:
        result = classifier(query, INTENT_LABELS)
        top_label = result["labels"][0].lower()
        logger.info(f"✅ [ZIC] HuggingFace Returned Intent: {top_label}")

        return top_label if top_label in INTENT_LABELS else "ask"

    except Exception as e:
        logger.error(f"❌ [ZIC] Error during classification: {e}")
        return "ask"
