from django.core.management.base import BaseCommand
from accounts.models import Staff
from django.contrib.auth.hashers import make_password

class Command(BaseCommand):
    help = 'Updates placeholder data for Staff model'

    def handle(self, *args, **kwargs):
        for index, staff in enumerate(Staff.objects.all(), start=1):
            updated = False
            if staff.email.endswith('@example.com'):
                staff.email = f'staff_{index}@yourdomain.com'  # Replace with a more appropriate domain
                updated = True
            if staff.username == 'defaultuser':
                staff.username = f'staff_{index}'
                updated = True
            if staff.password.startswith('pbkdf2_sha256$260000$defaultpasswordhash'):
                staff.password = make_password(f'changemelater{index}')  # Set a temporary password
                updated = True
            if updated:
                staff.save()
                self.stdout.write(self.style.SUCCESS(f'Updated staff member: {staff.username}'))

        self.stdout.write(self.style.SUCCESS('Staff records update completed.'))