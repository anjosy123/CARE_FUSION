import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib
import logging
from .preprocessor import HealthDataPreprocessor
from .exceptions import *

logger = logging.getLogger(__name__)

class RiskPredictor:
    def __init__(self):
        try:
            # Load trained models
            self.risk_model = joblib.load('accounts/ml/models/risk_model.pkl')
            self.scaler = joblib.load('accounts/ml/models/scaler.pkl')
            self.preprocessor = HealthDataPreprocessor()
        except FileNotFoundError as e:
            logger.error(f"Model loading failed: {str(e)}")
            raise ModelNotFoundError("Required ML models not found")

    def validate_input(self, record):
        """Validate input data"""
        required_fields = ['blood_pressure', 'pulse_rate', 'temperature']
        missing_fields = [field for field in required_fields 
                         if not getattr(record, field, None)]
        
        if missing_fields:
            raise InvalidInputError(
                f"Missing required fields: {', '.join(missing_fields)}"
            )

    def predict_risks(self, record):
        """Predict various risk scores with error handling"""
        try:
            # Validate input
            self.validate_input(record)

            # Preprocess data
            try:
                vitals = self.preprocessor.preprocess_vital_signs(record)
                risk_factors = self.preprocessor.preprocess_risk_factors(record)
            except Exception as e:
                logger.error(f"Preprocessing failed: {str(e)}")
                raise DataPreprocessingError("Failed to preprocess patient data")

            # Combine features
            features = pd.concat([vitals, risk_factors], axis=1)

            # Scale features
            try:
                scaled_features = self.scaler.transform(features)
            except Exception as e:
                logger.error(f"Feature scaling failed: {str(e)}")
                raise DataPreprocessingError("Failed to scale features")

            # Make predictions
            try:
                predictions = {
                    'fall_risk_score': float(self.risk_model.predict(scaled_features)[0]),
                    'pressure_ulcer_risk': float(self.risk_model.predict(scaled_features)[0]),
                    'deterioration_risk': float(self.risk_model.predict(scaled_features)[0]),
                    'overall_health_score': float(self.risk_model.predict(scaled_features)[0])
                }

                # Validate predictions
                for key, value in predictions.items():
                    if not (0 <= value <= 10):
                        logger.warning(f"Invalid prediction for {key}: {value}")
                        predictions[key] = min(max(value, 0), 10)

                return predictions

            except Exception as e:
                logger.error(f"Prediction failed: {str(e)}")
                raise ModelPredictionError("Failed to generate risk predictions")

        except MLPredictionError as e:
            logger.error(f"ML Prediction Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in risk prediction: {str(e)}")
            raise MLPredictionError("Unexpected error in risk prediction")