import joblib
import numpy as np

MODEL_PATH = "model/risk_model.pkl"

model = joblib.load(MODEL_PATH)


def predict_risk(followed, isolated, threat, unsafe):

    features = np.array([[
        int(followed),
        int(isolated),
        int(threat),
        int(unsafe)
    ]])

    prediction = model.predict(features)[0]

    probabilities = model.predict_proba(features)[0]

    classes = model.classes_

    risk_score = round(
        sum(
            probabilities[i] * {
                "LOW": 15,
                "MEDIUM": 50,
                "HIGH": 85
            }[classes[i]]
            for i in range(len(classes))
        ),
        2
    )

    return prediction, risk_score