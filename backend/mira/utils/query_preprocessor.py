import json
import os
import re
from nltk import ngrams

# Load stopwords from external JSON file
STOPWORDS_PATH = os.path.join(os.path.dirname(__file__), "stopwords.json")


try:
    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        all_stopwords = json.load(f)
except Exception as e:
    print(f"Failed to load stopwords: {e}")
    all_stopwords = {"en": [], "it": []}

def extract_keywords(query: str) -> list:
    """
    Cleans and extracts important keywords and phrases from a user's query.
    Removes stopwords and unnecessary noise like punctuation.
    """
    if not query:
        return []

    # 🧹 Lowercase the query
    query = query.lower()

    # 🧹 Remove punctuation (keep only letters, numbers, spaces)
    query = re.sub(r"[^a-zA-Z0-9\s]", "", query)

    # 🧹 Split into words
    words = query.split()

    # 🧹 Generate n-grams (2-word phrases)
    n_grams = [" ".join(ngram) for ngram in ngrams(words, 2)]

    # 🧹 Combine single words and n-grams
    all_phrases = words + n_grams

    # 🧹 Determine language (basic heuristic)
    lang = "it" if any(word in all_stopwords["it"] for word in words) else "en"
    stopwords = set(all_stopwords.get(lang, []))

    # 🧹 Filter out stopwords
    keywords = [word for word in all_phrases if word not in stopwords]

    return keywords
