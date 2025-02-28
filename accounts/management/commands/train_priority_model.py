from django.core.management.base import BaseCommand
from accounts.ml.model_trainer import PriorityPredictor
from django_q.tasks import schedule
from django_q.models import Schedule

class Command(BaseCommand):
    help = 'Train the patient priority prediction model using CSV data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            help='Name of the CSV file in the data directory',
            default='patient_data.csv'
        )

    def handle(self, *args, **kwargs):
        try:
            self.stdout.write('Starting model training...')
            
            # Initialize trainer with CSV file
            trainer = PriorityPredictor()
            if kwargs['csv']:
                trainer.csv_file = kwargs['csv']
            
            # Train the model and get metrics
            metrics = trainer.train()
            
            self.stdout.write(self.style.SUCCESS(
                f"Model training completed successfully\n"
                f"Accuracy: {metrics['accuracy']:.2%}\n"
                f"Training Accuracy: {metrics['training_accuracy']:.2%}"
            ))
            
            # Schedule daily updates
            schedule_name = 'update_priority_predictions'
            Schedule.objects.filter(name=schedule_name).delete()
            Schedule.objects.create(
                name=schedule_name,
                func='accounts.ml.tasks.update_priority_predictions',
                schedule_type=Schedule.DAILY
            )
            
            self.stdout.write(self.style.SUCCESS('Daily prediction updates scheduled'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during model training: {str(e)}')
            ) 