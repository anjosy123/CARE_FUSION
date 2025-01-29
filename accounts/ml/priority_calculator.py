from .risk_predictor import RiskPredictor

class VisitPriorityCalculator:
    def __init__(self):
        self.risk_predictor = RiskPredictor()
        
    def calculate_priority(self, record):
        """Calculate visit priority score"""
        # Get risk predictions
        risks = self.risk_predictor.predict_risks(record)
        
        # Calculate priority score (example algorithm)
        priority_score = (
            risks['deterioration_risk'] * 0.4 +
            risks['fall_risk_score'] * 0.3 +
            risks['pressure_ulcer_risk'] * 0.2 +
            (10 - risks['overall_health_score']) * 0.1
        )
        
        return float(priority_score)

    def get_next_visit_recommendation(self, priority_score):
        """Calculate recommended days until next visit based on priority score"""
        if priority_score >= 8.0:
            return 1  # Next day
        elif priority_score >= 6.0:
            return 3  # Within 3 days
        elif priority_score >= 4.0:
            return 7  # Within a week
        else:
            return 14  # Within two weeks