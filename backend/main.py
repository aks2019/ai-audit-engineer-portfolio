from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import joblib
from pathlib import Path
import uvicorn

app = FastAPI(title="AI Audit Engine - Backend")

# Allow Streamlit Cloud to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load models once when app starts
MODELS_DIR = Path("models")
iso_model = joblib.load(MODELS_DIR / "isolation_forest.joblib")
xgb_model = joblib.load(MODELS_DIR / "xgboost_risk_regressor.joblib")

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    df = pd.read_csv(file.file) if file.filename.endswith(".csv") else pd.read_excel(file.file)
    
    # Reuse your existing feature logic (simple version)
    from src.audit_anomaly_detector.features.engineer_features import engineer_features
    processed = engineer_features(df)
    
    X = processed[["amount"] + list(processed.columns[processed.columns.str.contains("zscore|ratio|flag|risk")])]
    
    anomaly_score = -iso_model.predict(X)
    processed["anomaly_score"] = anomaly_score
    processed["anomaly_probability"] = 1 - ((iso_model.decision_function(X) - iso_model.decision_function(X).min()) / 
                                           (iso_model.decision_function(X).max() - iso_model.decision_function(X).min()))
    
    # Add SHAP explanation (simplified)
    processed["risk_explanation"] = processed.apply(
        lambda row: f"Flagged because amount is {row.get('amount_ratio', 0):.1f}× historical average", axis=1
    )
    
    return processed.to_dict(orient="records")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)