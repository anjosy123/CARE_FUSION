import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
import joblib

class HealthRiskModelTrainer:
    def __init__(self):
        self.scaler = StandardScaler()
        self.risk_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.priority_model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            random_state=42
        )

    def prepare_data(self, records):
        """
        Prepare data from PatientVisitRecord for training
        """
        data = []
        for record in records:
            # Extract features
            features = {
                'blood_pressure_systolic': float(record.blood_pressure.split('/')[0]) if record.blood_pressure else 0,
                'blood_pressure_diastolic': float(record.blood_pressure.split('/')[1]) if record.blood_pressure else 0,
                'pulse_rate': record.pulse_rate if record.pulse_rate else 0,
                'temperature': float(record.temperature) if record.temperature else 0,
                'respiratory_rate': record.respiratory_rate if record.respiratory_rate else 0,
                'oxygen_saturation': record.oxygen_saturation if record.oxygen_saturation else 0,
                'pain_score': record.pain_score if record.pain_score else 0,
                'activity_level': record.activity_level if record.activity_level else 0,
                'weight': float(record.weight) if record.weight else 0,
                'mood_status': record.mood_status if record.mood_status else 0
            }
            data.append(features)
        
        return pd.DataFrame(data)

    def train_models(self, X_train, y_train):
        """
        Train risk and priority models
        """
        # Scale features
        X_scaled = self.scaler.fit_transform(X_train)
        
        # Train risk model
        self.risk_model.fit(X_scaled, y_train['risk'])
        
        # Train priority model
        self.priority_model.fit(X_scaled, y_train['priority'])
        
        # Save models
        joblib.dump(self.risk_model, 'accounts/ml/models/risk_model.pkl')
        joblib.dump(self.priority_model, 'accounts/ml/models/priority_model.pkl')
        joblib.dump(self.scaler, 'accounts/ml/models/scaler.pkl')

    def evaluate_models(self, X_test, y_test):
        """
        Evaluate model performance
        """
        X_scaled = self.scaler.transform(X_test)
        
        # Evaluate risk model
        risk_pred = self.risk_model.predict(X_scaled)
        risk_mse = mean_squared_error(y_test['risk'], risk_pred)
        risk_r2 = r2_score(y_test['risk'], risk_pred)
        
        # Evaluate priority model
        priority_pred = self.priority_model.predict(X_scaled)
        priority_mse = mean_squared_error(y_test['priority'], priority_pred)
        priority_r2 = r2_score(y_test['priority'], priority_pred)
        
        return {
            'risk_mse': risk_mse,
            'risk_r2': risk_r2,
            'priority_mse': priority_mse,
            'priority_r2': priority_r2
        }