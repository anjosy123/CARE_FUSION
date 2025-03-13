from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User,AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.utils.crypto import get_random_string
import uuid
from datetime import datetime
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
import random
from datetime import timedelta

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('patient', 'Patient'),
        ('caretaker', 'Caretaker'),
    )
    
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('Organizations', on_delete=models.SET_NULL, null=True, blank=True)
    usertype = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='patient')
    patient_name = models.CharField(max_length=100, null=True, blank=True)  # For storing patient name if registered by caretaker

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

    # Add priority score fields
    visit_priority_score = models.FloatField(default=0.0)
    fall_risk_score = models.FloatField(default=0.0)
    deterioration_risk = models.FloatField(default=0.0)
    overall_health_score = models.FloatField(default=0.0)

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

    
class UserLocation(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.TextField()
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Location for {self.user.username}"
    
class CaretakerDetails(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='caretaker_details')
    caretaker_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50)
    patient_name = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.caretaker_name} - Caretaker for {self.patient_name}"

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
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    def set_password(self, raw_password):
        self.org_password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.org_password)
    
    def __str__(self):
        return self.org_name

class ServiceRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected')
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(
        Organizations, 
        on_delete=models.CASCADE,
        related_name='service_requests'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(default=timezone.now)
    phone = models.CharField(max_length=10)
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
    
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    
    organization = models.ForeignKey('Organizations', on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=15)  # Changed from phone_number to phone
    address = models.TextField(blank=True)
    qualifications = models.TextField(blank=True)
    temporary_password = models.CharField(max_length=128, null=True, blank=True)
    designation = models.CharField(max_length=50, default='Unspecified')
    experience = models.PositiveIntegerField(default=0)
    email = models.EmailField(unique=True)
    profile_pic = models.ImageField(upload_to='staff_profiles/', null=True, blank=True)
    is_email_confirmed = models.BooleanField(default=False)
    confirmation_token = models.CharField(max_length=64, blank=True, null=True)
    must_change_password = models.BooleanField(default=True)
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
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class TeamVisit(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='visits')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_visits')
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.TextField(blank=True, null=True)
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

    def update_expired_status(self):
        """Update status to CANCELLED if visit time has passed"""
        current_datetime = timezone.now()
        visit_datetime = timezone.make_aware(datetime.combine(self.scheduled_date, self.end_time))
        
        if (current_datetime > visit_datetime + timezone.timedelta(hours=2) and 
            self.status == 'SCHEDULED'):
            self.status = 'CANCELLED'
            self.cancellation_reason = 'Automatically cancelled due to expired schedule'
            self.save()
            return True
        return False

    @classmethod
    def update_all_expired_visits(cls):
        """Update all expired scheduled visits"""
        current_datetime = timezone.now()
        expired_visits = cls.objects.filter(
            status='SCHEDULED',
            scheduled_date__lt=current_datetime.date()
        )
        
        for visit in expired_visits:
            visit.update_expired_status()

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
    role = models.CharField(max_length=50)  # Role in the team
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'staff')  # Prevent duplicate assignments
        
    def __str__(self):
        return f"{self.staff.get_full_name()} - {self.team.name}"

class NotificationPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    email_enabled = models.BooleanField(default=True)
    appointment_reminders = models.BooleanField(default=True)
    class Meta:
        db_table = 'accounts_notificationpreferences'

    def __str__(self):
        return f"Notification preferences for {self.user.username}"

class PrivacySettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='privacy_settings')
    profile_visible = models.BooleanField(default=True)

class TaxiDriver(models.Model):
    VEHICLE_TYPES = [
        ('SEDAN', 'Sedan'),
        ('SUV', 'SUV'),
        ('VAN', 'Van'),
        ('AMBULANCE', 'Ambulance')
    ]
    
    # Add user fields directly to TaxiDriver
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    password = models.CharField(max_length=128)  # For hashed password
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE)
    vehicle_number = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    license_number = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'taxi_drivers'

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.vehicle_number}"
    
    def is_on_leave(self, date=None):
        from .utils import get_driver_leave_status
        return get_driver_leave_status(self, date)
    
    def can_take_bookings(self):
        from .utils import can_driver_take_bookings
        return can_driver_take_bookings(self)
    
    def get_current_leave(self):
        today = timezone.now().date()
        return DriverLeave.objects.filter(
            driver=self,
            status='APPROVED',
            start_date__lte=today,
            end_date__gte=today
        ).first()

    

class FareStage(models.Model):
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE)
    start_km = models.IntegerField()
    end_km = models.IntegerField()
    base_fare = models.DecimalField(max_digits=10, decimal_places=2)
    per_km_rate = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class TaxiBooking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('DRIVER_ASSIGNED', 'Driver Assigned'),
        ('STARTED', 'Started'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE)
    driver = models.ForeignKey(TaxiDriver, on_delete=models.SET_NULL, null=True)
    pickup_location = models.TextField()
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    drop_location = models.TextField()
    drop_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    drop_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    booking_time = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2)
    final_fare = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=100, null=True)
    payment_status = models.CharField(max_length=20, default='PENDING')
    emergency_notes = models.TextField(blank=True)
    patient_rating = models.IntegerField(null=True)
    patient_feedback = models.TextField(blank=True)

    class Meta:
        db_table = 'taxi_bookings'

    def __str__(self):
        return f"Booking #{self.id} - {self.patient.get_full_name()}"



class DriverLeave(models.Model):
    LEAVE_TYPES = [
        ('SICK', 'Sick Leave'),
        ('PERSONAL', 'Personal Leave'),
        ('EMERGENCY', 'Emergency Leave')
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected')
    ]
    
    driver = models.ForeignKey(TaxiDriver, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    response_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'driver_leaves'
        ordering = ['-created_at']
        
class DriverEarning(models.Model):
    driver = models.ForeignKey(TaxiDriver, on_delete=models.CASCADE)
    booking = models.OneToOneField(TaxiBooking, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_transfer_id = models.CharField(max_length=100, null=True, blank=True)
    transfer_status = models.CharField(max_length=20, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'driver_earnings'

class TaxiComplaint(models.Model):
    COMPLAINT_TYPES = [
        ('BEHAVIOR', 'Driver Behavior'),
        ('DELAY', 'Delay'),
        ('CLEANLINESS', 'Vehicle Cleanliness'),
        ('OTHER', 'Other')
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected')
    ]
    
    booking = models.ForeignKey('TaxiBooking', on_delete=models.CASCADE)
    complaint_type = models.CharField(max_length=20, choices=COMPLAINT_TYPES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'taxi_complaints'

class PatientVisitRecord(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visit_records')
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    visit_date = models.DateTimeField()
    
    # Vital signs
    blood_pressure = models.CharField(max_length=20, null=True, blank=True)
    pulse_rate = models.IntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    respiratory_rate = models.IntegerField(null=True, blank=True)
    oxygen_saturation = models.IntegerField(null=True, blank=True)  # New field
    
    # Pain assessment
    pain_score = models.IntegerField(null=True, blank=True)
    pain_location = models.CharField(max_length=255, null=True, blank=True)  # Increased from 100
    pain_character = models.CharField(max_length=255, null=True, blank=True)  # Increased from 100
    
    # Medical conditions and symptoms
    medical_conditions = models.TextField(null=True, blank=True)
    symptoms = models.TextField(null=True, blank=True)
    
    # Medications and notes
    medications = models.TextField(null=True, blank=True)
    clinical_notes = models.TextField(null=True, blank=True)
    
    # Activity and Mobility (New section)
    activity_level = models.IntegerField(choices=[
        (1, 'Bedbound'),
        (2, 'Wheelchair bound'),
        (3, 'Walks with assistance'),
        (4, 'Walks independently')
    ], null=True, blank=True)
    
    # Nutrition Status (New section)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    appetite = models.IntegerField(choices=[
        (1, 'Poor'),
        (2, 'Fair'),
        (3, 'Good')
    ], null=True, blank=True)
    
    # Mental Status (New section)
    consciousness_level = models.CharField(max_length=50, null=True, blank=True)
    mood_status = models.IntegerField(choices=[
        (1, 'Depressed'),
        (2, 'Anxious'),
        (3, 'Normal'),
        (4, 'Elevated')
    ], null=True, blank=True)
    
    # Risk Scores (New section for ML)
    fall_risk_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    pressure_ulcer_risk = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    deterioration_risk = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    overall_health_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    
    # Visit Priority (New field for ML)
    visit_priority_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    next_visit_recommendation = models.IntegerField(null=True, blank=True)  # Days until next recommended visit
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Add these fields for priority prediction
    priority_score = models.FloatField(null=True, blank=True)
    priority_updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-visit_date']

    def __str__(self):
        return f"Visit for {self.patient.get_full_name()} on {self.visit_date}"

    def calculate_risk_scores(self):
        """
        Calculate risk scores using ML models
        """
        # This method will be implemented with ML logic
        pass

    def predict_next_visit(self):
        """
        Predict optimal next visit date using ML
        """
        # This method will be implemented with ML logic
        pass

    def get_visit_priority(self):
        """
        Calculate visit priority based on risk scores and other factors
        """
        # This method will be implemented with ML logic
        pass


class EmergencyContact(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    relationship = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.relationship})"

class Meta:
    permissions = [
        ("can_schedule_visits", "Can schedule team visits"),
        ("can_export_reports", "Can export priority reports"),
        ("can_retrain_model", "Can retrain priority model"),
    ]

# Add these new models after the existing models

class MedicalEquipment(models.Model):
    CONDITION_CHOICES = [
        ('NEW', 'New'),
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair')
    ]
    
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RENTED', 'Rented'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('RETIRED', 'Retired')
    ]
    
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE, related_name='equipment')
    name = models.CharField(max_length=200)
    description = models.TextField()
    equipment_type = models.CharField(max_length=100)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    rental_price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    serial_number = models.CharField(max_length=100, unique=True)
    maintenance_history = models.TextField(blank=True)
    
    # Add these new fields
    primary_image = models.ImageField(upload_to='equipment_images/', null=True, blank=True)
    additional_images = models.JSONField(default=list, blank=True)  # Store paths to additional images
    
    quantity = models.PositiveIntegerField(default=1, help_text="Number of units available")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

class EquipmentRental(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected')
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded'),
        ('FAILED', 'Failed')
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    equipment = models.ForeignKey(MedicalEquipment, on_delete=models.CASCADE)
    daily_rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    rental_start_date = models.DateField(null=True, blank=True)
    rental_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    rejection_reason = models.TextField(blank=True)
    delivery_address = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    # Add these new fields
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient.username} - {self.equipment.name}"

    def get_usage_duration(self):
        """Calculate the total days of usage"""
        if self.status == 'ACTIVE':
            return (timezone.now().date() - self.rental_start_date).days
        return 0

    def get_current_bill_amount(self):
        """Calculate the current bill amount based on usage"""
        days = self.get_usage_duration()
        return days * self.daily_rental_price

    def get_usage_periods(self):
        """Get the usage history in periods"""
        try:
            return self.usage_periods.all().order_by('-start_date')
        except Exception:
            return []

    def get_total_amount(self):
        """Get total amount paid/due for this rental"""
        return self.get_current_bill_amount()

    def get_full_name(self):
        """Get patient's full name"""
        return f"{self.patient.first_name} {self.patient.last_name}"

class RentalPayment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('INITIAL', 'Initial Payment'),
        ('EXTENSION', 'Rental Extension'),
        ('DAMAGE', 'Damage Charges'),
        ('REFUND', 'Security Deposit Refund')
    ]
    
    rental = models.ForeignKey(EquipmentRental, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    razorpay_payment_id = models.CharField(max_length=100)
    razorpay_order_id = models.CharField(max_length=100)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=EquipmentRental.PAYMENT_STATUS_CHOICES)
    
    def __str__(self):
        return f"Payment for {self.rental} - {self.payment_type}"

class EquipmentDelivery(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('ARRIVED', 'Arrived at Location'),
        ('OTP_VERIFIED', 'OTP Verified'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )
    
    rental = models.ForeignKey('EquipmentRental', on_delete=models.CASCADE)
    volunteer = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    delivery_notes = models.TextField(blank=True)
    
    # Location tracking
    volunteer_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    volunteer_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # OTP verification
    delivery_otp = models.CharField(max_length=6, null=True, blank=True)
    otp_generated_at = models.DateTimeField(null=True, blank=True)
    otp_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def generate_otp(self):
        """Generate a 6-digit OTP and save it"""
        self.delivery_otp = ''.join(random.choices('0123456789', k=6))
        self.otp_generated_at = timezone.now()
        self.save()
        return self.delivery_otp
    
    def verify_otp(self, otp):
        """Verify the provided OTP"""
        if not self.delivery_otp:
            return False
        if self.otp_generated_at < timezone.now() - timedelta(minutes=10):
            return False
        return self.delivery_otp == otp

class RentalPaymentAnalytics(models.Model):
    organization = models.ForeignKey(Organizations, on_delete=models.CASCADE)
    date = models.DateField()
    total_payments = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    security_deposits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rental_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunds_issued = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        unique_together = ['organization', 'date']
        
    @classmethod
    def update_analytics(cls, payment):
        """Update analytics when a payment is made"""
        date = payment.payment_date.date()
        org = payment.rental.equipment.organization
        
        analytics, created = cls.objects.get_or_create(
            organization=org,
            date=date,
            defaults={
                'total_payments': 0,
                'total_amount': 0,
                'security_deposits': 0,
                'rental_fees': 0,
                'refunds_issued': 0
            }
        )
        
        analytics.total_payments += 1
        analytics.total_amount += payment.amount
        
        if payment.payment_type == 'INITIAL':
            analytics.security_deposits += payment.rental.deposit_amount
            analytics.rental_fees += (payment.amount - payment.rental.deposit_amount)
        elif payment.payment_type == 'REFUND':
            analytics.refunds_issued += payment.amount
            
        analytics.save()

@receiver(post_save, sender=EquipmentRental)
def update_equipment_quantity(sender, instance, created, **kwargs):
    """
    Signal to update equipment quantity when rental payment is processed
    """
    try:
        if not created and instance.payment_status == 'PAID' and instance.status == 'APPROVED':
            with transaction.atomic():
                equipment = instance.equipment
                if equipment.quantity > 0:
                    # Store previous quantity for message
                    previous_quantity = equipment.quantity
                    
                    # Update quantity
                    equipment.quantity -= 1
                    equipment.save()
                    
                    # Update rental status to ACTIVE
                    instance.status = 'ACTIVE'
                    instance.save()
                    
                    # Create a notification for the organization
                    from django.contrib import messages
                    from django.contrib.messages import constants as message_levels
                    
                    # Store message in session for display on manage_equipment page
                    from django.core.cache import cache
                    message_key = f'equipment_update_{equipment.id}'
                    message = f'Equipment "{equipment.name}" quantity updated from {previous_quantity} to {equipment.quantity} units.'
                    cache.set(message_key, message, 300)  # Store for 5 minutes
                    
    except Exception as e:
        print(f"Error updating equipment quantity: {str(e)}")

class MonthlyRentalPayment(models.Model):
    rental = models.ForeignKey(EquipmentRental, on_delete=models.CASCADE, related_name='monthly_payments')
    month_start_date = models.DateField()
    month_end_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('OVERDUE', 'Overdue'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled')
    ], default='PENDING')
    payment_date = models.DateTimeField(null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    warning_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-month_start_date']

    def is_overdue(self):
        if self.payment_status == 'PENDING':
            return timezone.now().date() > (self.month_end_date + timedelta(days=7))
        return False

class RentalUsagePeriod(models.Model):
    rental = models.ForeignKey(EquipmentRental, on_delete=models.CASCADE, related_name='usage_periods')
    start_date = models.DateField()
    end_date = models.DateField()
    duration = models.IntegerField()  # in days
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
