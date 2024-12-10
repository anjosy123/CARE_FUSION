from django import forms
from .models import Service
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ServiceRequest,Service,Staff,PatientAssignment,Prescription,Appointment, Team, TeamVisit, TeamMessage, VisitChecklist, VisitNote
from django.core.exceptions import ValidationError
from datetime import datetime
import os
import imghdr

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
        
        # Add help text for profile pic
        self.fields['profile_pic'].help_text = 'Only JPG/JPEG files are allowed. Maximum file size: 5MB'
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Exclude current instance when checking for duplicates during update
        if self.instance.pk:
            if Staff.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
                raise ValidationError("A staff member with this email already exists.")
        else:
            if Staff.objects.filter(email=email).exists():
                raise ValidationError("A staff member with this email already exists.")
        return email

    def clean_profile_pic(self):
        profile_pic = self.cleaned_data.get('profile_pic')
        
        if profile_pic:
            # Check file size (5MB limit)
            if profile_pic.size > 5 * 1024 * 1024:
                raise ValidationError("Image file size must be less than 5MB.")
            
            # Get file extension
            ext = os.path.splitext(profile_pic.name)[1].lower()
            
            # Check if it's a jpg/jpeg file
            valid_extensions = ['.jpg', '.jpeg']
            
            if ext not in valid_extensions:
                raise ValidationError("Only JPG/JPEG files are allowed.")
            
            # Additional check for actual file content
            try:
                # Read the first few bytes to check file type
                file_type = imghdr.what(profile_pic)
                if file_type not in ['jpeg', 'jpg']:
                    raise ValidationError("Invalid image format. Only JPG/JPEG files are allowed.")
            except Exception:
                raise ValidationError("Could not verify image format. Please upload a valid JPG/JPEG file.")

        return profile_pic

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not phone:
            raise ValidationError("Phone number is required.")
        
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Check if phone number is exactly 10 digits
        if len(phone) < 10:
            raise ValidationError("Phone number must be 10 digits. Current number is too short.")
        elif len(phone) > 10:
            raise ValidationError("Phone number must be 10 digits. Current number is too long.")
        
        # Validate that the phone number starts with a valid digit (optional)
        if not phone.startswith(('6', '7', '8', '9')):
            raise ValidationError("Phone number must start with 6, 7, 8, or 9.")
        
        # Format the phone number before saving (optional)
        formatted_phone = f"{phone[:5]}{phone[5:]}"
        
        return formatted_phone
    
    

    def clean_experience(self):
        experience = self.cleaned_data.get('experience')
        
        if experience is not None:
            if experience < 0:
                raise ValidationError("Experience cannot be negative.")
            if experience > 50:
                raise ValidationError("Experience cannot be more than 50 years.")
                
        return experience

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        
        if first_name:
            # Remove extra whitespace
            first_name = ' '.join(first_name.split())
            
            # Check if contains only letters and spaces
            if not all(char.isalpha() or char.isspace() for char in first_name):
                raise ValidationError("Name should only contain letters and spaces.")
            
            # Check minimum length
            if len(first_name) < 2:
                raise ValidationError("Name is too short.")
                
            # Check maximum length
            if len(first_name) > 30:
                raise ValidationError("Name is too long.")
                
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        
        if last_name:
            # Remove extra whitespace
            last_name = ' '.join(last_name.split())
            
            # Check if contains only letters and spaces
            if not all(char.isalpha() or char.isspace() for char in last_name):
                raise ValidationError("Name should only contain letters and spaces.")
            
            # Check minimum length
            if len(last_name) < 2:
                raise ValidationError("Name is too short.")
                
            # Check maximum length
            if len(last_name) > 30:
                raise ValidationError("Name is too long.")
                
        return last_name
        
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

    def clean_doctor_referral(self):
        file = self.cleaned_data.get('doctor_referral')
        if file:
            # Add file validation if needed
            if file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size must be under 5MB")
            
            # Check file extension
            valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError("Only PDF and image files are allowed")
        return file

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

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }