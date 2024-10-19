from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ServiceRequest,Service,Staff,PatientAssignment,Prescription,Appointment
from django.core.exceptions import ValidationError
from datetime import datetime

User = get_user_model()

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'role', 'designation', 'experience', 'profile_pic']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email field required
        self.fields['email'].required = True
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Staff.objects.filter(email=email).exists():
            raise ValidationError("A staff member with this email already exists.")
        return email
        
class StaffStatusForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['is_active']

class PatientAssignmentForm(forms.ModelForm):
    class Meta:
        model = PatientAssignment
        fields = ['patient', 'staff']
        
        
class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ['service', 'doctor_referral', 'additional_notes']
        widgets = {
            'additional_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if organization:
            self.fields['service'].queryset = Service.objects.filter(organization=organization, is_active=True)

    def clean_doctor_referral(self):
        doctor_referral = self.cleaned_data.get('doctor_referral')
        if doctor_referral:
            if not doctor_referral.name.lower().endswith('.pdf'):
                raise ValidationError("Only PDF files are allowed for doctor's referral.")
        return doctor_referral


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'is_active']
        
        
class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medication', 'dosage', 'frequency', 'start_date', 'end_date', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class AppointmentForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    patient = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=False), required=False)

    class Meta:
        model = Appointment
        fields = ['purpose', 'notes']

    def __init__(self, *args, **kwargs):
        is_staff = kwargs.pop('is_staff', False)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['date'].initial = self.instance.date_time.date()
            self.fields['time'].initial = self.instance.date_time.time()
        if not is_staff:
            del self.fields['patient']

    def save(self, commit=True):
        instance = super().save(commit=False)
        date = self.cleaned_data.get('date')
        time = self.cleaned_data.get('time')
        if date and time:
            instance.date_time = datetime.combine(date, time)
        if commit:
            instance.save()
        return instance

