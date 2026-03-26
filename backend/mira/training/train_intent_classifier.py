import json

import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
import joblib
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
# Load dataset
df = pd.read_csv("../data/intent_dataset.csv")


# Train/test split (optional for validation)
X = df["Query"]
y = df["Label"]
# Split into train/test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

# Build pipeline
model = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("clf", LogisticRegression(max_iter=1000))
])
# Cross-validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=cv, scoring="f1_weighted")
print(f"\n📊 Cross-validation F1 (weighted): {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

# Create logs folder if it doesn't exist
os.makedirs("../../logs", exist_ok=True)

log_entry = {
    "timestamp": datetime.utcnow().isoformat(),
    "cv_mean_f1": round(cv_scores.mean(), 3),
    "cv_std_f1": round(cv_scores.std(), 3),
    "cv_scores": [round(score, 3) for score in cv_scores.tolist()]
}

with open("../../logs/cv_scores_log.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(log_entry) + "\n")

# Train model
model.fit(X_train, y_train)
# Evaluate on test set
y_pred = model.predict(X_test)

# Classification Report
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred, labels=model.classes_)
print("\n🧩 Confusion Matrix:")
print(cm)

# Plot Confusion Matrix
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=model.classes_, yticklabels=model.classes_)
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.title("Confusion Matrix")
plt.tight_layout()
os.makedirs("../../logs", exist_ok=True)
plt.savefig("../../logs/confusion_matrix.png")
plt.show()

# Save model
os.makedirs("../model", exist_ok=True)
joblib.dump(model, "../model/intent_classifier.pkl")

print("✅ Intent classifier trained and saved as 'intent_classifier.pkl'")
