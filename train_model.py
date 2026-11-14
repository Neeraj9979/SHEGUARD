import numpy as np
import os
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


# Generate demonstration dataset
np.random.seed(42)

X = np.random.randint(0, 2, size=(2000, 4))


# Features:
# 0 = Followed
# 1 = Isolated
# 2 = Threat
# 3 = Feels unsafe

scores = (
    X[:, 0] * 35 +
    X[:, 1] * 20 +
    X[:, 2] * 35 +
    X[:, 3] * 10
)


# Generate demonstration labels
y = np.where(
    scores >= 60, "HIGH",
    np.where(scores >= 30, "MEDIUM", "LOW")
)


# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


# Create Random Forest model
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,
    random_state=42,
    class_weight="balanced"
)


# Train model
model.fit(X_train, y_train)


# Evaluate model
predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

print("Model Accuracy:", accuracy)

print("\nClassification Report:")
print(classification_report(y_test, predictions))


# Save model
os.makedirs("model", exist_ok=True)

joblib.dump(model, "model/risk_model.pkl")

print("\nModel trained and saved successfully!")