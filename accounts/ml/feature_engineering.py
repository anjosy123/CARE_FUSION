from datetime import datetime
import numpy as np

class FeatureExtractor:
    def extract_features(self, patient_record):
        """Extract relevant features from a patient visit record"""
        features = {
            'pain_score': patient_record.pain_score or 0,
            'oxygen_saturation': patient_record.oxygen_saturation or 95,
            'activity_level': patient_record.activity_level or 4,
            'appetite': patient_record.appetite or 2,
            'mood_status': patient_record.mood_status or 3,
            'fall_risk_score': float(patient_record.fall_risk_score or 0),
            'pressure_ulcer_risk': float(patient_record.pressure_ulcer_risk or 0),
            'deterioration_risk': float(patient_record.deterioration_risk or 0),
            'overall_health_score': float(patient_record.overall_health_score or 0),
        }
        
        # Extract blood pressure
        if patient_record.blood_pressure:
            try:
                systolic, diastolic = map(int, patient_record.blood_pressure.split('/'))
                features['systolic_bp'] = systolic
                features['diastolic_bp'] = diastolic
            except:
                features['systolic_bp'] = 120
                features['diastolic_bp'] = 80
        else:
            features['systolic_bp'] = 120
            features['diastolic_bp'] = 80
        
        # Add vital signs
        features.update({
            'pulse_rate': patient_record.pulse_rate or 75,
            'temperature': float(patient_record.temperature or 37.0),
            'respiratory_rate': patient_record.respiratory_rate or 16,
        })
        
        # Calculate days since last visit
        if patient_record.visit_date:
            days_since_visit = (datetime.now().date() - patient_record.visit_date.date()).days
            features['days_since_visit'] = days_since_visit
        else:
            features['days_since_visit'] = 0
            
        return features

    def _normalize_value(self, value, min_val, max_val):
        """Normalize a value between 0 and 1"""
        if value is None:
            return 0.5
        return (value - min_val) / (max_val - min_val)