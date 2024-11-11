from django import forms
from .models import Service
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ServiceRequest,Service,Staff,PatientAssignment,Prescription,Appointment, Team, TeamVisit, TeamMessage, VisitChecklist, VisitNote
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
            'medication': forms.TextInput(attrs={
                'id': 'medication',
                'class': 'form-control',
                'placeholder': 'Enter medication name'
            }),
            'dosage': forms.TextInput(attrs={
                'id': 'dosage',
                'class': 'form-control',
                'placeholder': 'Enter dosage'
            }),
            'frequency': forms.TextInput(attrs={
                'id': 'frequency',
                'class': 'form-control',
                'placeholder': 'Enter frequency'
            }),
            'start_date': forms.DateInput(attrs={
                'id': 'start_date',
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'id': 'end_date',
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'id': 'notes',
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter any additional notes'
            }),
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
    
# palliative organization team management

class TeamForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=Staff.objects.none(),  # We'll set this in __init__
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrollable-checklist'}),
        required=False
    )

    class Meta:
        model = Team
        fields = ['name', 'members']

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super(TeamForm, self).__init__(*args, **kwargs)
        if organization:
            self.fields['members'].queryset = Staff.objects.filter(organization=organization)

class TeamVisitForm(forms.ModelForm):
    patient = forms.ModelChoiceField(queryset=User.objects.none())

    class Meta:
        model = TeamVisit
        fields = ['team', 'patient', 'scheduled_date', 'start_time', 'end_time', 'notes']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super(TeamVisitForm, self).__init__(*args, **kwargs)
        if organization:
            self.fields['team'].queryset = Team.objects.filter(organization=organization)
            # Get patients who have made service requests to this organization
            patient_ids = ServiceRequest.objects.filter(organization=organization).values_list('patient', flat=True).distinct()
            self.fields['patient'].queryset = User.objects.filter(id__in=patient_ids)

class RescheduleTeamVisitForm(forms.Form):
    new_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    new_start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    new_end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    reason = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned_data = super().clean()
        new_start_time = cleaned_data.get('new_start_time')
        new_end_time = cleaned_data.get('new_end_time')

        if new_start_time and new_end_time and new_start_time >= new_end_time:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned_data
    

class TeamMessageForm(forms.ModelForm):
    class Meta:
        model = TeamMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3}),
        }
        
class VisitChecklistForm(forms.ModelForm):
    class Meta:
        model = VisitChecklist
        fields = ['pain_assessment', 'medication_review', 'symptom_management', 'psychological_support', 'family_education']

class VisitNoteForm(forms.ModelForm):
    class Meta:
        model = VisitNote
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
        }

class AppointmentRequestForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['date_time', 'purpose', 'notes']
        widgets = {
            'date_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }