from django.core.management.base import BaseCommand
from accounts.models import PatientVisitRecord
from accounts.ml.model_trainer import PriorityPredictor

class Command(BaseCommand):
    help = 'Update priority scores for all patient records'

    def handle(self, *args, **kwargs):
        try:
            self.stdout.write('Starting priority score updates...')
            
            # Initialize predictor
            predictor = PriorityPredictor()
            
            # Get all records
            records = PatientVisitRecord.objects.all()
            self.stdout.write(f'Found {records.count()} records to update')
            
            # Update each record
            updated = 0
            for record in records:
                try:
                    # Calculate priority score
                    priority_score = predictor.predict_from_record(record)
                    
                    # Update record
                    record.priority_score = priority_score
                    record.save()
                    
                    updated += 1
                    if updated % 10 == 0:
                        self.stdout.write(f'Updated {updated} records...')
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error updating record {record.id}: {str(e)}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated} records')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during update: {str(e)}')
            ) 