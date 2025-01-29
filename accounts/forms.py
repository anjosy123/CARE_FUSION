from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ServiceRequest,Service,Staff,PatientAssignment,Prescription,Appointment, Team, TeamVisit, TeamMessage, VisitChecklist, VisitNote, TaxiDriver, TaxiBooking, FareStage, DriverLeave, DriverEarning, TaxiComplaint
from django.core.exceptions import ValidationError
from datetime import datetime
import os
import imghdr
from django.utils import timezone

User = get_user_model()

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'designation', 'experience', 'profile_pic', 'gender', 'address', 'qualifications']
        
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

    def clean_phone(self):  # Changed from clean_phone_number to clean_phone
        phone = self.cleaned_data.get('phone')  # Changed from phone_number to phone
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
    class Meta:
        model = Team
        fields = ['name', 'members']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'members': forms.CheckboxSelectMultiple()
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields['members'].queryset = Staff.objects.filter(organization=organization)

    def clean_members(self):
        members = self.cleaned_data.get('members')
        if members and members.count() < 2:
            raise forms.ValidationError("A team must have at least 2 members.")
        return members

from django import forms
from django.utils import timezone
from .models import TeamVisit, Team, User

class TeamVisitForm(forms.ModelForm):
    # Custom patient field with proper label display
    patient = forms.ModelChoiceField(
        queryset=User.objects.none(),
        empty_label="Select a Patient",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Select Patient'
        }),
        label="Patient"
    )

    class Meta:
        model = TeamVisit
        fields = ['team', 'patient', 'scheduled_date', 'start_time', 'end_time', 'notes', 'status']
        widgets = {
            'team': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Select Team'
            }),
            'scheduled_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'start_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Enter any additional notes here...'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        
        # Make all fields required except notes
        for field_name, field in self.fields.items():
            if field_name not in ['notes']:
                field.required = True
        
        # Add help texts and labels
        field_helps = {
            'team': 'Select the team that will conduct the visit',
            'patient': 'Select the patient to be visited',
            'scheduled_date': 'Select the date for the team visit',
            'start_time': 'Select the start time of the visit',
            'end_time': 'Select the end time of the visit',
            'notes': 'Add any additional notes or instructions (optional)',
            'status': 'Current status of the visit'
        }

        field_labels = {
            'team': 'Select Team',
            'patient': 'Select Patient',
            'scheduled_date': 'Visit Date',
            'start_time': 'Start Time',
            'end_time': 'End Time',
            'notes': 'Additional Notes',
            'status': 'Visit Status'
        }

        # Apply help texts and labels
        for field_name, help_text in field_helps.items():
            self.fields[field_name].help_text = help_text
        
        for field_name, label in field_labels.items():
            self.fields[field_name].label = label

        # Filter querysets if organization is provided
        if organization:
            # Filter teams
            self.fields['team'].queryset = Team.objects.filter(
                organization=organization,
                is_active=True
            ).order_by('name')

            # Get current date for filtering
            current_date = timezone.now().date()
            
            # Get patients who already have scheduled visits
            patients_with_visits = TeamVisit.objects.filter(
                team__organization=organization,
                scheduled_date__gte=current_date,
                status__in=['SCHEDULED', 'IN_PROGRESS']
            ).values_list('patient', flat=True)

            # Filter and set the patient queryset
            patient_queryset = User.objects.filter(
                service_requests__organization=organization,
                service_requests__status='APPROVED',
                is_active=True
            ).exclude(
                id__in=patients_with_visits
            ).exclude(
                is_staff=True,
                is_superuser=True
            ).distinct().order_by('first_name', 'last_name')

            self.fields['patient'].queryset = patient_queryset
            self.fields['patient'].label_from_instance = lambda obj: (
                f"{obj.first_name} {obj.last_name}"
            )

        # Set default status for new visits
        if not self.instance.pk:
            self.fields['status'].initial = 'SCHEDULED'

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        scheduled_date = cleaned_data.get('scheduled_date')
        team = cleaned_data.get('team')
        patient = cleaned_data.get('patient')

        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError({
                    'end_time': "End time must be after start time"
                })

        if scheduled_date:
            if scheduled_date < timezone.now().date():
                raise forms.ValidationError({
                    'scheduled_date': "Visit cannot be scheduled in the past"
                })

        # Check if patient already has a visit scheduled for this date
        if patient and scheduled_date:
            existing_visit = TeamVisit.objects.filter(
                patient=patient,
                scheduled_date=scheduled_date,
                status__in=['SCHEDULED', 'IN_PROGRESS']
            ).exclude(pk=self.instance.pk if self.instance else None).first()
            
            if existing_visit:
                raise forms.ValidationError(
                    f"Patient already has a visit scheduled with {existing_visit.team.name} "
                    f"on {scheduled_date} from {existing_visit.start_time.strftime('%I:%M %p')} "
                    f"to {existing_visit.end_time.strftime('%I:%M %p')}"
                )

        # Check for team availability
        if team and scheduled_date and start_time and end_time:
            overlapping_visits = TeamVisit.objects.filter(
                team=team,
                scheduled_date=scheduled_date,
                status__in=['SCHEDULED', 'IN_PROGRESS']
            ).exclude(pk=self.instance.pk if self.instance else None)

            for visit in overlapping_visits:
                if (start_time < visit.end_time and end_time > visit.start_time):
                    raise forms.ValidationError(
                        f"Team is already scheduled for another visit during this time slot "
                        f"({visit.start_time.strftime('%I:%M %p')} - {visit.end_time.strftime('%I:%M %p')})"
                    )

        return cleaned_data

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

class DriverForm(forms.ModelForm):
    class Meta:
        model = TaxiDriver
        fields = [
            'vehicle_number',
            'vehicle_type',
            'license_number',
            'organization'
        ]

class TaxiBookingForm(forms.ModelForm):
    class Meta:
        model = TaxiBooking
        fields = ['pickup_location', 'drop_location', 'emergency_notes']
        widgets = {
            'emergency_notes': forms.Textarea(attrs={'rows': 3}),
            'pickup_location': forms.Textarea(attrs={'rows': 2}),
            'drop_location': forms.Textarea(attrs={'rows': 2}),
        }

class FareStageForm(forms.ModelForm):
    class Meta:
        model = FareStage
        fields = ['start_km', 'base_fare', 'per_km_rate']
        widgets = {
            'start_km': forms.NumberInput(attrs={'class': 'form-control'}),
            'base_fare': forms.NumberInput(attrs={'class': 'form-control'}),
            'per_km_rate': forms.NumberInput(attrs={'class': 'form-control'})
        }
        
class DriverLeaveForm(forms.ModelForm):
    class Meta:
        model = DriverLeave
        fields = ['start_date', 'end_date', 'leave_type', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }
        
class DriverEarningForm(forms.ModelForm):
    class Meta:
        model = DriverEarning
        fields = ['amount', 'booking']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'booking': forms.Select(attrs={'class': 'form-control'})
        }
        
class ComplaintForm(forms.ModelForm):
    class Meta:
        model = TaxiComplaint
        fields = ['booking', 'complaint_type', 'description']
        widgets = {
            'booking': forms.Select(attrs={'class': 'form-control'}),
            'complaint_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }