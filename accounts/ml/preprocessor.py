import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from ..models import PatientVisitRecord

class HealthDataPreprocessor:
    def __init__(self):
        self.scaler = StandardScaler()
        
    def preprocess_vital_signs(self, record):
        """Process vital signs data"""
        vitals = {
            'blood_pressure_systolic': float(record.blood_pressure.split('/')[0]) if record.blood_pressure else 0,
            'blood_pressure_diastolic': float(record.blood_pressure.split('/')[1]) if record.blood_pressure else 0,
            'pulse_rate': record.pulse_rate if record.pulse_rate else 0,
            'temperature': float(record.temperature) if record.temperature else 0,
            'respiratory_rate': record.respiratory_rate if record.respiratory_rate else 0,
            'oxygen_saturation': record.oxygen_saturation if record.oxygen_saturation else 0
        }
        return pd.DataFrame([vitals])

    def preprocess_risk_factors(self, record):
        """Process risk factors"""
        risk_factors = {
            'pain_score': record.pain_score if record.pain_score else 0,
            'activity_level': record.activity_level if record.activity_level else 0,
            'appetite': record.appetite if record.appetite else 0,
            'mood_status': record.mood_status if record.mood_status else 0,
            'weight': float(record.weight) if record.weight else 0
        }
        return pd.DataFrame([risk_factors])

    def scale_features(self, features_df):
        """Scale numerical features"""
        return self.scaler.fit_transform(features_df)