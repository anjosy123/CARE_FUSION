from django.utils import timezone
from django.db import models
from django.contrib.auth.models import BaseUserManager,User,AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.utils.crypto import get_random_string
from django.db.models import Max
import uuid
from django.conf import settings
from datetime import timedelta

class User(AbstractUser):
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('Organizations', on_delete=models.SET_NULL, null=True, blank=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        return self.username


# class OrganizationManager(BaseUserManager):
    def create_user(self, org_email, org_name, org_address, org_phone, org_password=None):
        if not org_email:
            raise ValueError('The Email field is required')

        email = self.normalize_email(org_email)
        user = self.model(
            org_email=email,
            org_name=org_name,
            org_address=org_address,
            org_phone=org_phone,
        )
        user.set_password(org_password)
        user.save(using=self._db)
        return user

    def create_superuser(self, org_email, org_name, org_address, org_phone, org_password=None):
        user = self.create_user(
            org_email,
            org_name,
            org_address,
            org_phone,
            org_password=org_password,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user

class Contact(models.Model):
    name = models.CharField(max_length=30)
    email = models.EmailField()
    phoneNumber = models.CharField(max_length=12)
    description = models.TextField()

class Organizations(models.Model):
    org_email = models.EmailField(unique=True)
    org_regid = models.CharField(max_length=100, unique=True)
    org_name = models.CharField(max_length=100)
    org_address = models.TextField()
    org_phone = models.CharField(max_length=15)
    org_password = models.CharField(max_length=128, default='defaultpassword')
    approve = models.BooleanField(default=False)
    pincode = models.CharField(max_length=10)
    is_email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True) 
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    teams = models.ManyToManyField('Team', related_name='team_organizations', blank=True)
    
    def set_password(self, raw_password):
        self.org_password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.org_password)
    
    # groups = models.ManyToManyField(
    #     'auth.Group',
    #     related_name='organization_set',  # Add related_name to avoid conflict
    #     blank=True,
    #     help_text='The groups this user belongs to.',
    #     verbose_name='groups',
    # )
    # user_permissions = models.ManyToManyField(
    #     'auth.Permission',
    #     related_name='organization_set',  # Add related_name to avoid conflict
    #     blank=True,
    #     help_text='Specific permissions for this user.',
    #     verbose_name='user permissions',
    # )

    # objects = OrganizationManager()

    # USERNAME_FIELD = 'org_email'
    # REQUIRED_FIELDS = ['org_email', 'org_name', 'org_address', 'org_phone']

    def __str__(self):
        return self.org_name

class ServiceRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_requests')
    organization = models.ForeignKey('Organizations', on_delete=models.CASCADE, related_name='service_requests')
    created_at = models.DateTimeField(default=timezone.now)
    doctor_referral = models.FileField(upload_to='referrals/', null=True, blank=True)
    additional_notes = models.TextField(blank=True)
    service = models.ForeignKey('Service', on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Service Request for {self.patient.username} to {self.organization.org_name}"
    
    def save(self, *args, **kwargs):
        self.status = self.status.upper()  # Ensure status is always uppercase
        super().save(*args, **kwargs)
    

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE, related_name='services')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.organization.org_name}"

    class Meta:
        unique_together = ['name', 'organization']
        ordering = ['name']
        
# Staff details
class Staff(AbstractUser):
    ROLE_CHOICES = (
        ('DOCTOR', 'Doctor'),
        ('NURSE', 'Nurse'),
        ('VOLUNTEER', 'Volunteer'),
    )
    organization = models.ForeignKey('Organizations', on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    temporary_password = models.CharField(max_length=128, null=True, blank=True)
    phone_number = models.CharField(max_length=15, default='0000000000')
    designation = models.CharField(max_length=50, default='Unspecified')
    experience = models.PositiveIntegerField(default=0)
    email = models.EmailField(unique=True)
    profile_pic = models.ImageField(upload_to='staff_profiles/', null=True, blank=True)
    is_email_confirmed = models.BooleanField(default=False)
    confirmation_token = models.CharField(max_length=64, blank=True, null=True)
    must_change_password = models.BooleanField(default=True)

    # Make username nullable temporarily
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)

    def get_display_name(self):
        if self.get_full_name():
            return self.get_full_name()
        return self.username
    
    def generate_confirmation_token(self):
        self.confirmation_token = get_random_string(64)
        self.save()
    
class PatientAssignment(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_assignments')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='patient_assignments')
    assigned_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE, related_name='patient_assignments')
    last_interaction = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    medical_history = models.TextField(blank=True)

    class Meta:
        unique_together = ['patient', 'staff']

    def __str__(self):
        return f"{self.patient.get_full_name()} assigned to {self.staff.get_full_name()}"

    def update_last_interaction(self):
        self.last_interaction = timezone.now()
        self.save()
    
    def add_medical_history_entry(self, entry):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        self.medical_history += f"\n[{timestamp}] {entry}"
        self.save()

class Prescription(models.Model):
    patient_assignment = models.ForeignKey(PatientAssignment, on_delete=models.CASCADE, related_name='prescriptions')
    medication = models.CharField(max_length=100)
    dosage = models.CharField(max_length=50)
    frequency = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.medication} for {self.patient_assignment.patient.get_full_name()}"
    
class Appointment(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('BOOKED', 'Booked'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    
    patient_assignment = models.ForeignKey('PatientAssignment', on_delete=models.CASCADE, related_name='appointments')
    date_time = models.DateTimeField()
    purpose = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='AVAILABLE')
    cancellation_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appointment for {self.patient_assignment.patient.get_full_name()} on {self.date_time}"
    
class Notification(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    organization = models.ForeignKey('Organizations', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        recipient = self.patient.get_full_name()
        return f"Notification for {recipient}: {self.message[:50]}..."
        
class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient}"
    

# palliative organization team management

class Team(models.Model):
    name = models.CharField(max_length=100)
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE, related_name='organization_teams')
    members = models.ManyToManyField(Staff, related_name='staff_teams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class TeamVisit(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='visits')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_visits')
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=[
        ('SCHEDULED', 'Scheduled'),
        ('COMPLETED', 'Completed'),
        ('POSTPONED', 'Postponed'),
        ('CANCELLED', 'Cancelled')
    ], default='SCHEDULED')
    notes = models.TextField(blank=True)
    rescheduled_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='rescheduled_to')
    rescheduled_reason = models.TextField(blank=True)

    def reschedule(self, new_date, new_start_time, new_end_time, reason=''):
        new_visit = TeamVisit.objects.create(
            team=self.team,
            patient=self.patient,
            scheduled_date=new_date,
            start_time=new_start_time,
            end_time=new_end_time,
            status='SCHEDULED',
            notes=self.notes,
            rescheduled_from=self,
            rescheduled_reason=reason
        )
        self.status = 'RESCHEDULED'
        self.save()
        return new_visit

    def is_reschedulable(self):
        return self.scheduled_date > timezone.now().date() and self.status == 'SCHEDULED'

    def __str__(self):
        return f"{self.team.name} visit to {self.patient.get_full_name()} on {self.scheduled_date}"
    @classmethod
    def check_conflicts(cls, team, date, start_time, end_time, exclude_id=None):
        conflicts = cls.objects.filter(
            team=team,
            scheduled_date=date,
            status='SCHEDULED'
        ).exclude(id=exclude_id)

        return conflicts.filter(
            models.Q(start_time__lt=end_time, end_time__gt=start_time) |
            models.Q(start_time=start_time, end_time=end_time)
        ).exists()

    def reschedule(self, new_date, new_start_time, new_end_time, reason=''):
        if self.check_conflicts(self.team, new_date, new_start_time, new_end_time, exclude_id=self.id):
            raise ValueError("The new time slot conflicts with an existing visit.")

        new_visit = TeamVisit.objects.create(
            team=self.team,
            patient=self.patient,
            scheduled_date=new_date,
            start_time=new_start_time,
            end_time=new_end_time,
            status='SCHEDULED',
            notes=self.notes,
            rescheduled_from=self,
            rescheduled_reason=reason
        )
        self.status = 'RESCHEDULED'
        self.save()
        return new_visit

class TeamVisitRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected')
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    requested_date = models.DateField(null=True, blank=True)  # Made optional
    purpose = models.CharField(max_length=200, null=True, blank=True)  # Made optional
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"Team Visit Request by {self.patient.username} for {self.team.name}"

class TeamSchedule(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField()
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ['team', 'date']

    def __str__(self):
        return f"{self.team.name} schedule for {self.date}"

class TeamMessage(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        sender_name = self.sender.get_full_name() if self.sender else self.organization.org_name
        return f"Message from {sender_name} to {self.team.name} at {self.created_at}"

class VisitChecklist(models.Model):
    team_visit = models.OneToOneField('TeamVisit', on_delete=models.CASCADE, related_name='checklist')
    pain_assessment = models.BooleanField(default=False)
    medication_review = models.BooleanField(default=False)
    symptom_management = models.BooleanField(default=False)
    psychological_support = models.BooleanField(default=False)
    family_education = models.BooleanField(default=False)

    def __str__(self):
        return f"Checklist for visit on {self.team_visit.scheduled_date}"

class VisitNote(models.Model):
    team_visit = models.ForeignKey('TeamVisit', on_delete=models.CASCADE, related_name='visit_notes')
    staff = models.ForeignKey('Staff', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Note by {self.staff} for visit on {self.team_visit.scheduled_date}"

class TeamDashboard(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    username = models.EmailField(unique=True)
    password = models.CharField(max_length=128)

    class Meta:
        unique_together = ['team', 'staff']

    def __str__(self):
        return f"Dashboard for {self.staff.get_full_name()} in {self.team.name}"

class NotificationPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    email_enabled = models.BooleanField(default=True)
    appointment_reminders = models.BooleanField(default=True)

class PrivacySettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='privacy_settings')
    profile_visible = models.BooleanField(default=True)




