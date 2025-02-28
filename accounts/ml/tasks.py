from accounts.models import PatientVisitRecord
from accounts.ml.model_trainer import PriorityPredictor
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def update_priority_predictions():
    """Update priority scores for all patient records"""
    try:
        print("Starting priority predictions update...")
        
        # Initialize and train predictor
        predictor = PriorityPredictor()
        print("Training model on dataset...")
        metrics = predictor.train()
        print(f"Model trained. Accuracy: {metrics['accuracy']:.2%}")
        
        # Get all patient records
        records = PatientVisitRecord.objects.all()
        print(f"Processing {records.count()} patient records...")
        
        updated_count = 0
        for record in records:
            try:
                # Predict priority score
                priority_score = predictor.predict_from_record(record)
                
                # Update record
                record.priority_score = priority_score
                record.priority_updated_at = timezone.now()
                record.save()
                
                updated_count += 1
                if updated_count % 10 == 0:
                    print(f"Processed {updated_count} records...")
                
            except Exception as e:
                print(f"Error updating record {record.id}: {str(e)}")
                logger.error(f"Error updating priority for record {record.id}: {str(e)}")
        
        print(f"Completed updating {updated_count} records")
                
    except Exception as e:
        print(f"Error in priority update task: {str(e)}")
        logger.error(f"Error in priority update task: {str(e)}") 