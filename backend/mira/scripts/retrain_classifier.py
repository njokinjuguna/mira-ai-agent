import os
import json
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

# Paths
BASE_DIR = os.path.dirname(__file__)
DATASET_PATH = os.path.join(BASE_DIR, "..", "data", "intent_dataset.csv")
LOG_PATH = os.path.join(BASE_DIR, "..", "logs", "intent_logs.jsonl")
MODEL_PATH = os.path.join(BASE_DIR, "..", "model", "intent_classifier.pkl")

# Load existing dataset
df = pd.read_csv(DATASET_PATH)

# Load verified new samples from logs
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        new_entries = [json.loads(line) for line in f if line.strip()]

    new_df = pd.DataFrame(new_entries)
    if not new_df.empty:
        new_df = new_df.rename(columns={"query": "Query", "intent": "Label"})
        combined = pd.concat([df, new_df], ignore_index=True)
        combined.drop_duplicates(subset=["Query"], inplace=True)
        df = combined

# Train classifier
X = df["Query"]
y = df["Label"]
model = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("clf", LogisticRegression(max_iter=1000))
])
model.fit(X, y)

# Save updated model
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
joblib.dump(model, MODEL_PATH)

# Optionally overwrite dataset with expanded one
df.to_csv(DATASET_PATH, index=False)

print("✅ Retrained model saved. Dataset updated with new log entries.")
