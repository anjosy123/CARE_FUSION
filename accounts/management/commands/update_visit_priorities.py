from django.core.management.base import BaseCommand
from accounts.models import PatientVisitRecord

class Command(BaseCommand):
    help = 'Update visit priority scores'

    def handle(self, *args, **kwargs):
        records = PatientVisitRecord.objects.all()
        updated = 0

        for record in records:
            # Calculate visit priority score based on various factors
            score = 0
            
            # Blood pressure check
            if record.blood_pressure:
                try:
                    systolic, diastolic = map(int, record.blood_pressure.split('/'))
                    if systolic > 140 or systolic < 90:
                        score += 2
                except:
                    pass

            # Oxygen saturation
            if record.oxygen_saturation:
                if record.oxygen_saturation < 95:
                    score += 2
                elif record.oxygen_saturation < 90:
                    score += 3

            # Pain score
            if record.pain_score:
                score += min(record.pain_score / 2, 3)  # Max 3 points for pain

            # Temperature
            if record.temperature:
                if record.temperature > 38.5 or record.temperature < 36:
                    score += 2

            # Normalize score to 0-10 range
            final_score = min(max(score, 0), 10)
            
            # Update record
            record.visit_priority_score = final_score
            record.save()
            updated += 1
            
            if updated % 10 == 0:
                self.stdout.write(f"Updated {updated} records...")

        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated} records')) 