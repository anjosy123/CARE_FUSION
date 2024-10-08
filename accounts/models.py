from django.utils import timezone
from django.db import models
from django.contrib.auth.models import BaseUserManager, User
from django.contrib.auth.hashers import make_password, check_password

# Create your models here.
# class Patient(models.Model):
#     name = models.CharField(max_length=100)
#     email = models.EmailField(unique=True)
#     password = models.CharField(max_length=100)
#     role = models.CharField(max_length=10, choices=[('patient','Patient'),('caretaker', 'Caretaker')])
    
#     def __str__(self):
#         return self.name
    
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
    org_regid = models.CharField(max_length=100, unique=True)
    org_email = models.EmailField(unique=True)
    org_name = models.CharField(max_length=100)
    org_address = models.TextField()
    org_phone = models.CharField(max_length=12)
    org_password = models.CharField(max_length=128, default='defaultpassword')  # Add default value
    approve=models.BooleanField(default=False) 
    pincode = models.CharField(max_length=10)
    
    
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

    def set_password(self, raw_password):
        self.org_password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.org_password)
    
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
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Service Request for {self.patient.username} to {self.organization.org_name}"
    
    def save(self, *args, **kwargs):
        self.status = self.status.upper()  # Ensure status is always uppercase
        super().save(*args, **kwargs)
    
