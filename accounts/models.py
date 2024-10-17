from django.utils import timezone
from django.db import models
from django.contrib.auth.models import BaseUserManager,User,AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.utils.crypto import get_random_string
from django.db.models import Max
import uuid

class User(AbstractUser):
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

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


class OrganizationManager(BaseUserManager):
    def create_user(self, org_username, org_email, org_name, org_address, org_phone, org_password=None):
        if not org_username:
            raise ValueError('The Username field is required')
        if not org_email:
            raise ValueError('The Email field is required')

        email = self.normalize_email(org_email)
        user = self.model(
            org_username=org_username,
            org_email=email,
            org_name=org_name,
            org_address=org_address,
            org_phone=org_phone,
        )
        user.set_password(org_password)
        user.save(using=self._db)
        return user

    def create_superuser(self, org_username, org_email, org_name, org_address, org_phone, org_password=None):
        user = self.create_user(
            org_username,
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
    org_phone = models.CharField(max_length=12)
    org_password = models.CharField(max_length=128, default='defaultpassword')
    approve = models.BooleanField(default=False)
    pincode = models.CharField(max_length=10)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    
    def set_password(self, raw_password):
        self.org_password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.org_password)
    
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='organization_set',  # Add related_name to avoid conflict
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='organization_set',  # Add related_name to avoid conflict
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    objects = OrganizationManager()

    USERNAME_FIELD = 'org_username'
    REQUIRED_FIELDS = ['org_email', 'org_name', 'org_address', 'org_phone']

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
    organization = models.ForeignKey('Organizations', on_delete=models.SET_NULL, related_name='staff_members', null=True, blank=True)
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
        return f"{self.patient.get_full_name() or self.patient.username} assigned to {self.staff.get_full_name()}"

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
    patient_assignment = models.ForeignKey(PatientAssignment, on_delete=models.CASCADE, related_name='appointments')
    date_time = models.DateTimeField()
    purpose = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appointment for {self.patient_assignment.patient.get_full_name()} on {self.date_time}"
    
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.message[:30]}"
        
class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient}"