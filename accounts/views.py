from django.shortcuts import render,redirect,get_object_or_404
from django.db.models.functions import TruncDate
from django.db import IntegrityError
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import logout, get_user_model
from django.urls import reverse
from django.core.mail import send_mail, get_connection, EmailMessage
from django.contrib.auth.hashers import check_password, make_password
from django.views.decorators.cache import cache_control, never_cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from care_fusion import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
import random, logging, os, string, uuid, razorpay, json
from django.utils import timezone
from .models import (
    Staff, Notification, Message, TeamVisitRequest, PrivacySettings, 
    Organizations, Contact, ServiceRequest, Service, Staff, PatientAssignment,
    Prescription, Appointment, Team, TeamVisit, TeamSchedule, User, 
    TeamMessage, VisitChecklist, VisitNote, TeamDashboard, PrivacySettings,
    TaxiDriver, TaxiBooking, FareStage, DriverLeave, DriverEarning, 
    TaxiComplaint, PatientVisitRecord, EmergencyContact  # Added EmergencyContact
)
from .forms import AppointmentRequestForm, ServiceRequestForm,ServiceForm,StaffForm,PatientAssignmentForm,PrescriptionForm,AppointmentForm,TeamForm, TeamVisitForm, RescheduleTeamVisitForm, TeamMessageForm, VisitChecklistForm, VisitNoteForm, ProfileUpdateForm,TeamVisit, TaxiBookingForm, DriverForm, FareStageForm, DriverLeaveForm, DriverEarningForm, ComplaintForm
from .utils import send_verification_email, send_appointment_email, calculate_distance, send_sms, notify_organization_about_leave, calculate_fare, create_razorpay_order, create_razorpay_account, notify_about_complaint, verify_razorpay_signature, transfer_to_driver, notify_payment_success, notify_driver_about_leave_response
from django.db.models import Q, Sum, Count, Avg
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str, force_bytes
from datetime import datetime, timedelta, time, date
from calendar import monthrange
from django.views.generic import ListView
from .decorators import staff_login_required, organization_login_required, patient_login_required, team_login_required
from smtplib import SMTPServerDisconnected
from django.db.utils import OperationalError
from django.db import transaction
from .ml.priority_calculator import VisitPriorityCalculator
from .ml.exceptions import InvalidInputError, ModelNotFoundError, MLPredictionError

def send_appointment_email(appointment, action, recipient='patient'):
    subject = f'Appointment {action.capitalize()}'
    to_email = appointment.patient_assignment.patient.email if recipient == 'patient' else appointment.patient_assignment.staff.email
    template = f'emails/appointment_{action}_{recipient}.html'
    
    context = {'appointment': appointment}
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [to_email], html_message=html_message)

logger = logging.getLogger(__name__)

User = get_user_model()

def home_view(request):
    return render(request, 'index.html')

def index(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

def organizations_home(request):
    return render(request, 'Organizations/organizations_home.html')

@never_cache
def doctor_dashboard(request):
    if request.session.get('role') != 'staff' or Staff.objects.get(id=request.session.get('staff_id')).role != 'DOCTOR':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')
    
    staff = Staff.objects.get(id=request.session.get('staff_id'))
    
    # Add the staff name to the session
    request.session['staff_name'] = staff.get_full_name()
    
    # Fetch active patient assignments for this doctor
    assignments = PatientAssignment.objects.filter(
        staff=staff,
        is_active=True
    ).select_related('patient')  # This will prefetch the related patient data

    upcoming_appointments = Appointment.objects.filter(
        patient_assignment__staff=staff,  # Changed from request.user to staff
        status='BOOKED'
    ).order_by('date_time')
    
    context = {
        'staff': staff,
        'assignments': assignments,
        'upcoming_appointments': upcoming_appointments,
        'appointment_form': AppointmentForm(),
    }
    
    return render(request, 'staff/doctor_dashboard.html', context)



def nurse_dashboard(request):
    if request.session.get('role') != 'staff' or Staff.objects.get(id=request.session.get('staff_id')).role != 'NURSE':
        return JsonResponse({
            'success': False,
            'message': "You don't have permission to access this page.",
            'redirect': reverse('login')
        })
    return render(request, 'staff/nurse_dashboard.html')

def volunteer_dashboard(request):
    if request.session.get('role') != 'staff' or Staff.objects.get(id=request.session.get('staff_id')).role != 'VOLUNTEER':
        return JsonResponse({
            'success': False,
            'message': "You don't have permission to access this page.",
            'redirect': reverse('login')
        })
    return render(request, 'staff/volunteer_dashboard.html')

def service_list(request):
    if 'org_id' not in request.session:
        return JsonResponse({
            'success': False,
            'message': "Please log in to access this page.",
            'redirect': reverse('org_login')
        })

    try:
        organization = Organizations.objects.get(id=request.session['org_id'])
        services = Service.objects.filter(organization=organization)
        return render(request, 'Organizations/service_list.html', {
            'services': services, 
            'org_name': organization.org_name
        })
    except Organizations.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': "Organization not found. Please log in again.",
            'redirect': reverse('org_login')
        })

def service_create(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('org_login')

    try:
        organization = Organizations.objects.get(id=request.session['org_id'])
        
        if request.method == 'POST':
            form = ServiceForm(request.POST)
            if form.is_valid():
                service = form.save(commit=False)
                service.organization = organization
                service.save()
                messages.success(request, 'Service created successfully.')
                return redirect('service_list')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = ServiceForm()
        
        return render(request, 'Organizations/service_form.html', {
            'form': form,
            'org_name': organization.org_name
        })
            
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('org_login')

def service_edit(request, pk):
    
    if not request.session.has_key('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('org_login')
    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
    except Organizations.DoesNotExist:
        messages.error(request, "You are not associated with any organization.")
        return redirect('org_login')

    service = get_object_or_404(Service, pk=pk, organization=organization)

    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated successfully.')
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    
    return render(request, 'Organizations/service_form.html', {'form': form, 'service': service})

def service_delete(request, pk):
    if not request.session.has_key('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('org_login')

    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
    except Organizations.DoesNotExist:
        messages.error(request, "You are not associated with any organization.")
        return redirect('org_login')

    service = get_object_or_404(Service, pk=pk, organization=organization)

    if request.method == 'POST':
        service.delete()
        messages.success(request, 'Service deleted successfully.')
        return redirect('service_list')
    
    return render(request, 'Organizations/service_confirm_delete.html', {'service': service})

def patient_details(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    patient = service_request.patient
    
    # Get the doctor's referral letter URL
    doctor_referral_url = None
    if service_request.doctor_referral:
        file_path = os.path.join(settings.MEDIA_ROOT, str(service_request.doctor_referral))
        if os.path.exists(file_path):
            doctor_referral_url = request.build_absolute_uri(service_request.doctor_referral.url)
    
    context = {
        'service_request': service_request,
        'patient': patient,
        'doctor_referral_url': doctor_referral_url,
    }
    return render(request, 'Organizations/patient_details.html', context)

@patient_login_required
def request_service(request, org_id):
    try:
        organization = get_object_or_404(Organizations, id=org_id)
        services = Service.objects.filter(organization=organization, is_active=True)
        
        if request.method == 'POST':
            service_id = request.POST.get('service')
            phone = request.POST.get('phone')
            doctor_referral = request.FILES.get('doctor_referral')
            additional_notes = request.POST.get('additional_notes')
            
            # Validate phone number
            if not phone or not phone.isdigit() or len(phone) != 10 or not phone.startswith(('6', '7', '8', '9')):
                messages.error(request, "Please enter a valid 10-digit phone number starting with 6-9.")
                return redirect('request_service', org_id=org_id)
            
            try:
                service = Service.objects.get(id=service_id, organization=organization)
                
                # Create service request
                ServiceRequest.objects.create(
                    patient=request.user,
                    organization=organization,
                    service=service,
                    phone=phone,  # Save the phone number
                    doctor_referral=doctor_referral,
                    additional_notes=additional_notes
                )
                
                messages.success(request, 'Service request submitted successfully!')
                return redirect('patients_dashboard')
                
            except Exception as e:
                messages.error(request, f'Error submitting request: {str(e)}')
        
        context = {
            'organization': organization,
            'services': services,
        }
        return render(request, 'Users/service_request_form.html', context)
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('patients_dashboard')


def get_service_request_detail(request, request_id):
    if not request.session.get('org_regid'):
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    service_request = get_object_or_404(ServiceRequest, id=request_id, organization_id=request.session['org_regid'])
    
    doctor_referral_url = None
    if service_request.doctor_referral:
        file_path = os.path.join(settings.MEDIA_ROOT, str(service_request.doctor_referral))
        if os.path.exists(file_path):
            doctor_referral_url = request.build_absolute_uri(service_request.doctor_referral.url)
    
    data = {
        'id': service_request.id,
        'patient_name': service_request.patient.get_full_name(),
        'status': service_request.status,
        'created_at': service_request.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'doctor_referral': doctor_referral_url,
        'additional_notes': service_request.additional_notes,
    }
    
    return JsonResponse(data)


def service_request_detail(request, request_id):
    if request.session.has_key('user_id'):
        user_id = request.session['user_id']
        service_request = get_object_or_404(ServiceRequest, id=request_id, patient_id=user_id)
        
        context = {
            'service_request': service_request,
        }
        return render(request, 'Users/service_request_detail.html', context)
    else:
        return redirect('login')
    
def edit_service_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id, patient_id=request.session['user_id'])
    if service_request.status.upper() != 'PENDING':
        messages.error(request, "You can't edit this request as it's no longer pending.")
        return redirect('service_request_detail', request_id=request_id)

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST, request.FILES, instance=service_request)
        if form.is_valid():
            form.save()
            messages.success(request, "Service request updated successfully.")
            return redirect('service_request_detail', request_id=request_id)
    else:
        form = ServiceRequestForm(instance=service_request)

    return render(request, 'Users/edit_service_request.html', {'form': form, 'service_request': service_request})

def delete_service_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id, patient_id=request.session['user_id'])
    if service_request.status.upper() != 'PENDING':
        messages.error(request, "You can't delete this request as it's no longer pending.")
    else:
        service_request.delete()
        messages.success(request, "Service request deleted successfully.")
    return redirect('service_requests')

def service_requests(request):
    if not request.session.has_key('user_id'):
        return redirect('login')

    user_id = request.session['user_id']
    status_filter = request.GET.get('status', 'ALL')
    # Base queryset
    service_requests = ServiceRequest.objects.filter(patient_id=user_id)
    
    # Apply status filter if not 'ALL'
    if status_filter and status_filter != 'ALL':
        service_requests = service_requests.filter(status=status_filter)
    
    # Order the queryset
    service_requests = service_requests.order_by('-created_at')

    # Pagination
    paginator = Paginator(service_requests, 10)  # Show 10 requests per page
    page = request.GET.get('page')

    try:
        service_requests = paginator.page(page)
    except PageNotAnInteger:
        service_requests = paginator.page(1)
    except EmptyPage:
        service_requests = paginator.page(paginator.num_pages)

    # Debug information
    print(f"Status filter: {status_filter}")
    # print(f"Total requests: {service_requests.count()}")
    print(f"Filtered requests: {len(service_requests)}")

    context = {
        'service_requests': service_requests,
        'current_status': status_filter,
        # 'total_requests': service_requests.count(),
    }
    
    return render(request, 'Users/service_requests.html', context)

def contact(request):
    if request.method=="POST":
        name = request.POST.get("fname")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        desc = request.POST.get("description")
        query = Contact(name=name,email=email,phoneNumber=phone,description=desc)
        query.save()
        messages.success(request,"Thanks For Reaching Us! We will get back you soon...")
        return redirect('contact')
    
    return render(request, 'contact.html')

def services(request):
    return render(request, 'Organizations/org_service_page.html')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_dashboard(request):
    if not request.session.get('user_id') or request.session.get('role') != 'admin':
        messages.error(request, "Please login as admin to access this page.")
        return redirect('login')

    try:
        # Get counts for dashboard cards
        total_patients = User.objects.exclude(
            email="carefusion.ai@gmail.com"
        ).count()

        # Get pending organizations (verified but not approved)
        pending_orgs = Organizations.objects.filter(
            approve=False, 
            is_email_verified=True
        ).order_by('-id')
        
        pending_count = pending_orgs.count()

        # Get approved organizations
        approved_orgs = Organizations.objects.filter(
            approve=True, 
            is_email_verified=True
        ).order_by('org_name')
        
        approved_count = approved_orgs.count()

        # Get all patients except admin
        patients = User.objects.exclude(
            email="carefusion.ai@gmail.com"
        ).order_by('-date_joined')

        context = {
            # Dashboard counts
            'total_patients': total_patients,
            'pending_organizations': pending_count,  # For the card count
            'approved_organizations': approved_count,
            
            # Table data
            'patients': patients,
            'pending_org_requests': pending_orgs,  # For the table data
            'approved_orgs': approved_orgs,
            'organizations': approved_orgs,  # For backward compatibility
            
            # Additional context
            'page_title': 'Admin Dashboard',
            'current_time': timezone.now(),
        }
        
        return render(request, 'Admin/admin.html', context)

    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('login')




def handlelogin(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("pass1")

        # Try to authenticate as Staff
        staff = Staff.objects.filter(email=email).first()
        if staff and check_password(password, staff.password):
            if not staff.is_email_confirmed:
                messages.error(request, "Please verify your email before logging in.")
                return redirect('login')
            
            request.session['staff_id'] = staff.id
            request.session['role'] = 'staff'
            request.session['org_id'] = staff.organization.id if staff.organization else None

            if staff.must_change_password:
                request.session['temp_login'] = True
                return redirect('change_staff_password')
            
            # Check if the staff member is part of any team
            team_memberships = TeamDashboard.objects.filter(staff=staff)
            if team_memberships.exists():
                request.session['team_ids'] = list(team_memberships.values_list('team_id', flat=True))
            
            # Role-based redirection for staff
            if staff.role == 'DOCTOR':
                return redirect('doctor_dashboard')
            elif staff.role == 'NURSE':
                return redirect('team_dashboard')
            elif staff.role == 'VOLUNTEER':
                return redirect('volunteer_dashboard')
            else:
                messages.error(request, "Invalid staff role.")
                return redirect('login')

        # Try to authenticate as User or Staff
        user = User.objects.filter(email=email).first() or Staff.objects.filter(email=email).first()
        
        if user and check_password(password, user.password):
            if isinstance(user, Staff):
                if not user.is_email_confirmed:
                    messages.error(request, "Please verify your email before logging in.")
                    return redirect('login')
                
                request.session['staff_id'] = user.id
                request.session['role'] = 'staff'
                request.session['org_id'] = user.organization.id if user.organization else None

                if user.must_change_password:
                    request.session['temp_login'] = True
                    return redirect('change_staff_password')
                
                # Check if the staff member is part of any team
                team_memberships = Team.objects.filter(members=user)
                if team_memberships.exists():
                    request.session['team_ids'] = list(team_memberships.values_list('id', flat=True))
                
                # Role-based redirection for staff
                if user.role == 'DOCTOR':
                    request.session['doctor_id'] = user.id
                    request.session['doctor_name'] = user.get_full_name()
                    return redirect('doctor_dashboard')
                elif user.role == 'NURSE':
                    return redirect('nurse_dashboard')
                elif user.role == 'VOLUNTEER':
                    return redirect('volunteer_dashboard')
                else:
                    messages.error(request, "Invalid staff role.")
                    return redirect('login')
            else:
                if not user.is_email_verified:
                    messages.error(request, "Please verify your email before logging in.")
                    return redirect('login')
                
                if user.email == "carefusion.ai@gmail.com":  # Admin email
                    request.session['user_id'] = user.id
                    request.session['role'] = 'admin'
                    return redirect('admin_dashboard')
                else:
                    request.session['user_id'] = user.id
                    request.session['role'] = 'user'
                    request.session['username'] = user.username
                    request.session['email'] = user.email
                    return redirect('patients_dashboard')

        # Try to authenticate as an Organization
        org_user = Organizations.objects.filter(org_email=email).first()
        if org_user and check_password(password, org_user.org_password):
            if not org_user.is_email_verified:
                messages.error(request, "Please verify your email before logging in.")
                return redirect('login')
            
            if org_user.approve:
                request.session['org_id'] = org_user.id
                request.session['org_regid'] = org_user.org_regid
                request.session['org_name'] = org_user.org_name
                request.session['role'] = 'organization'
                return redirect('palliatives_dashboard')
            else:
                messages.error(request, "Organization is not approved yet!")
                return redirect('login')

        messages.error(request, "Invalid email or password")
        return redirect('login')

    return render(request, 'Users/login.html')

def change_staff_password(request):
    if not request.session.get('temp_login'):
        return redirect('login')

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'staff/change_password.html')

        staff_id = request.session.get('staff_id')
        staff = Staff.objects.get(id=staff_id)
        staff.set_password(new_password)
        staff.must_change_password = False
        staff.save()

        del request.session['temp_login']
        messages.success(request, "Password changed successfully. Please log in with your new password.")
        return redirect('login')

    return render(request, 'staff/change_password.html')


def confirm_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        staff = Staff.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Staff.DoesNotExist):
        staff = None

    if staff and default_token_generator.check_token(staff, token):
        staff.is_email_confirmed = True
        
        # Generate a temporary password
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        staff.password = make_password(temp_password)
        staff.must_change_password = True
        staff.save()

        # Send login credentials email
        subject = 'Your Login Credentials'
        message = render_to_string('staff/login_credentials_email.html', {
            'staff': staff,
            'temp_password': temp_password,
        })
        send_mail(subject, message, 'from@example.com', [staff.email], html_message=message)

        messages.success(request, 'Your email has been confirmed. Check your inbox for login credentials.')
        return redirect('login')
    else:
        messages.error(request, 'The confirmation link was invalid or has expired.')
        return redirect('home')

@never_cache
def pending_requests(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    
    try:
        organization = Organizations.objects.get(id=org_id)
        pending_requests = ServiceRequest.objects.filter(organization=organization, status='PENDING').order_by('-created_at')
        
        context = {
            'organization': organization,
            'pending_requests': pending_requests,
            'active_page': 'service_requests',
        }
        
        return render(request, 'Organizations/pending_requests.html', context)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def patients_dashboard(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    if request.GET.get('view') == 'home':
        return render(request, 'Users/patient_home.html')

    user_id = request.session['user_id']
    patient = get_object_or_404(User, id=user_id)
    assignments = PatientAssignment.objects.filter(patient=patient, is_active=True).select_related('organization')

    # Existing organization query
    query = request.GET.get('q', '')
    organizations = Organizations.objects.filter(
        approve=True,
        is_active=True,
        is_email_verified=True
    )
    
    # Existing POST handling
    if request.method == 'POST':
        org_id = request.POST.get('organization_id')
        organization = get_object_or_404(Organizations, id=org_id)
        form = ServiceRequestForm(request.POST, request.FILES, organization=organization)
        if form.is_valid():
            service_request = form.save(commit=False)
            service_request.patient = patient
            service_request.organization = organization
            service_request.save()
            messages.success(request, 'Service request submitted successfully.')
            return redirect('patients_dashboard')
    else:
        form = ServiceRequestForm()
    
    if query:
        organizations = organizations.filter(org_name__icontains=query)

    # Existing queries
    service_requests = ServiceRequest.objects.filter(patient_id=user_id).order_by('-created_at')
    prescriptions = Prescription.objects.filter(patient_assignment__in=assignments).order_by('-start_date')
    all_appointments = Appointment.objects.filter(patient_assignment__in=assignments).order_by('date_time')
    booked_appointments = all_appointments.filter(status='BOOKED')
    available_appointments = all_appointments.filter(status='AVAILABLE')
    
    # New queries for enhanced functionality
    emergency_contacts = EmergencyContact.objects.filter(patient=patient)
    available_services = Service.objects.filter(organization__in=organizations)
    team_visits = TeamVisit.objects.filter(patient=patient).order_by('scheduled_date')
    
    # Existing medical history
    medical_history = [
        {'organization': assignment.organization, 'history': assignment.medical_history}
        for assignment in assignments if assignment.medical_history
    ]
    
    notifications = Notification.objects.filter(patient_id=user_id).order_by('-created_at')[:5]

    # Existing team queries
    assigned_teams = Team.objects.filter(
        organization__patient_assignments__patient=patient,
        organization__approve=True,
        organization__is_active=True
    ).distinct().prefetch_related('members')

    assigned_teams_count = Team.objects.filter(
        visits__patient=patient
    ).distinct().count()

    upcoming_appointments = booked_appointments.filter(
        date_time__gte=timezone.now(),
        date_time__lte=timezone.now() + timedelta(days=7)
    )

    recent_visit_requests = TeamVisitRequest.objects.filter(patient=patient).order_by('-created_at')[:5]
    pending_requests_count = ServiceRequest.objects.filter(
        patient_id=user_id,
        status='PENDING'
    ).count()

    latest_service_request = ServiceRequest.objects.filter(
        patient_id=user_id
    ).select_related('organization').last()

    # Pagination
    page_number = request.GET.get('page', 1)
    paginator = Paginator(service_requests, 10)
    service_requests_page = paginator.get_page(page_number)

    # Enhanced context with new data
    context = {
        # Existing context
        'patient': patient,
        'organizations': organizations,
        'query': query,
        'service_requests': service_requests_page,
        'prescriptions': prescriptions[:10],
        'booked_appointments': booked_appointments[:5],
        'available_appointments': available_appointments[:5],
        'medical_history': medical_history,
        'notifications': notifications,
        'assigned_teams': assigned_teams,
        'assigned_teams_count': assigned_teams_count,
        'upcoming_appointments': upcoming_appointments,
        'recent_visit_requests': recent_visit_requests,
        'form': form,
        'pending_requests_count': pending_requests_count,
        'latest_service_request': latest_service_request,
        
        # New context for enhanced functionality
        'emergency_contacts': emergency_contacts,
        'available_services': available_services,
        'team_visits': team_visits,
        'total_appointments': all_appointments.count(),
        'total_prescriptions': prescriptions.count(),
        'active_services': service_requests.filter(status='APPROVED').count(),
    }

    return render(request, 'Users/patients_dashboard.html', context)

@never_cache
def palliatives_dashboard(request):
    # Check if user is logged in
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    # Get organization
    try:
        organization = Organizations.objects.get(id=request.session['org_id'])
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')

    # Get dashboard context
    context = get_dashboard_context(organization)
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'staff_count': context['staff_count'],
            'assigned_patients_count': context['assigned_patients_count'],
            'pending_requests_count': context['pending_requests'].count(),
            'approved_requests_count': context['approved_requests'].count(),
            'rejected_requests_count': context['rejected_requests'].count(),
            'active_teams_count': context['active_teams_count'],
            'recent_assignments_html': render_to_string('Organizations/recent_assignments_partial.html', context),
            'pending_requests_html': render_to_string('Organizations/pending_requests_partial.html', context),
            'approved_requests_html': render_to_string('Organizations/approved_requests_partial.html', context),
            'rejected_requests_html': render_to_string('Organizations/rejected_requests_partial.html', context),
        })
    
    # Render full page for non-AJAX requests
    return render(request, 'Organizations/palliatives_dashboard.html', context)

def get_dashboard_context(organization):
    return {
        'organization': organization,
        'staff_count': Staff.objects.filter(organization=organization).count(),
        'assigned_patients_count': PatientAssignment.objects.filter(organization=organization, is_active=True).count(),
        'pending_requests': ServiceRequest.objects.filter(organization=organization, status='PENDING').order_by('-created_at'),
        'approved_requests': ServiceRequest.objects.filter(organization=organization, status='APPROVED').order_by('-created_at')[:5],
        'rejected_requests': ServiceRequest.objects.filter(organization=organization, status='REJECTED').order_by('-created_at')[:5],
        'recent_assignments': PatientAssignment.objects.filter(organization=organization, is_active=True).order_by('-assigned_date')[:5],
        'active_teams_count': Team.objects.filter(organization=organization).count(), 
        'pending_taxi_requests_count': TaxiBooking.objects.filter(
            organization=organization,
            status='PENDING'
        ).count(),
        'recent_taxi_bookings': TaxiBooking.objects.filter(
            organization=organization
        ).order_by('-booking_time')[:5]
    }

def staff_dashboard(request):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id)
    
    # Fetch active patient assignments for this staff member
    assignments = PatientAssignment.objects.filter(
        staff=staff,
        is_active=True
    ).select_related('patient')  # This will prefetch the related patient data

    # Fetch upcoming appointments
    upcoming_appointments = Appointment.objects.filter(
        patient_assignment__staff=staff,
        date_time__gte=timezone.now(),
        status='BOOKED'
    ).order_by('date_time')

    context = {
        'staff': staff,
        'assignments': assignments,
        'upcoming_appointments': upcoming_appointments,
    }
    
    if staff.role == 'DOCTOR':
        return render(request, 'staff/doctor_dashboard.html', context)
    elif staff.role == 'NURSE':
        return render(request, 'staff/nurse_dashboard.html', context)
    elif staff.role == 'VOLUNTEER':
        return render(request, 'staff/volunteer_dashboard.html', context)
    else:
        messages.error(request, "Invalid staff role.")
        return redirect('login')


def reschedule_appointment(request, appointment_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    appointment = get_object_or_404(Appointment, id=appointment_id, patient_assignment__staff=staff)

    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            old_datetime = appointment.date_time
            updated_appointment = form.save()
            
            # Send email to patient
            send_mail(
                'Appointment Rescheduled',
                f'Your appointment has been rescheduled from {old_datetime} to {updated_appointment.date_time}.',
                settings.DEFAULT_FROM_EMAIL,
                [updated_appointment.patient_assignment.patient.email],
                fail_silently=False,
            )
            
            # Create notification for patient dashboard
            Notification.objects.create(
                patient=updated_appointment.patient_assignment.patient,
                message=f'Your appointment has been rescheduled to {updated_appointment.date_time}.'
            )
            
            messages.success(request, 'Appointment rescheduled successfully.')
            return redirect('manage_appointments', assignment_id=updated_appointment.patient_assignment.id)
    else:
        form = AppointmentForm(instance=appointment)

    context = {
        'staff': staff,
        'appointment': appointment,
        'form': form,
    }
    return render(request, 'staff/doctor/reschedule_appointment.html', context)

    
def cancel_appointment(request, appointment_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    appointment = get_object_or_404(Appointment, id=appointment_id, patient_assignment__staff=staff)

    if request.method == 'POST':
        appointment.status = 'CANCELLED'
        appointment.save()
        
        # Send email to patient
        send_mail(
            'Appointment Cancelled',
            f'Your appointment scheduled for {appointment.date_time} has been cancelled.',
            settings.DEFAULT_FROM_EMAIL,
            [appointment.patient_assignment.patient.email],
            fail_silently=False,
        )
        
        # Create notification for patient dashboard
        Notification.objects.create(
            patient=appointment.patient_assignment.patient,
            message=f'Your appointment scheduled for {appointment.date_time} has been cancelled.'
        )
        
        messages.success(request, 'Appointment cancelled successfully.')
        return redirect('manage_appointments')

    context = {
        'staff': staff,
        'appointment': appointment,
    }
    return render(request, 'staff/cancel_appointment.html', context)
    
def patient_detail(request, assignment_id):
    staff = Staff.objects.get(user=request.user)
    assignment = PatientAssignment.objects.get(id=assignment_id, staff=staff)
    
    context = {
        'staff': staff,
        'assignment': assignment,
    }
    
    return render(request, 'staff/patient_detail.html', context)

def add_patient_note(request, assignment_id):
    if request.method == 'POST':
        assignment = PatientAssignment.objects.get(id=assignment_id, staff__user=request.user)
        note = request.POST.get('note')
        assignment.notes += f"\n{timezone.now()}: {note}"
        assignment.update_last_interaction()
        assignment.save()
        return redirect('patient_detail', assignment_id=assignment_id)
    return redirect('staff_dashboard')

@never_cache
def approved_rejected_requests(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    
    try:
        organization = Organizations.objects.get(id=org_id)
        approved_requests = ServiceRequest.objects.filter(organization=organization, status='APPROVED').order_by('-updated_at')
        rejected_requests = ServiceRequest.objects.filter(organization=organization, status='REJECTED').order_by('-updated_at')
        
        context = {
            'organization': organization,
            'approved_requests': approved_requests,
            'rejected_requests': rejected_requests,
            'active_page': 'service_requests',
        }
        
        return render(request, 'Organizations/approved_rejected_requests.html', context)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')
    

def verify_email(request, token, is_organization):
    try:
        if is_organization == '1':
            org = get_object_or_404(Organizations, email_verification_token=token)
            if not org.is_email_verified:
                org.is_email_verified = True
                org.save()
                messages.success(request, "Your organization email has been verified. Please wait for admin approval.")
            else:
                messages.info(request, "Your organization email has already been verified.")
        else:
            user = get_object_or_404(User, email_verification_token=token)
            if not user.is_email_verified:
                user.is_email_verified = True
                user.is_active = True
                user.save()
                messages.success(request, "Your email has been verified. You can now log in.")
            else:
                messages.info(request, "Your email has already been verified.")
    except Exception as e:
        messages.error(request, "Invalid verification link.")
    
    return redirect('login')


# User = get_user_model()

def handlesignup(request):
    if request.method == "POST":
        uname = request.POST.get("username")
        print(uname)
        firstname = request.POST.get("fname")
        lastname = request.POST.get("lname")
        email = request.POST.get("email")
        password = request.POST.get("pass1")
        confirmpassword = request.POST.get("pass2")

        # Check if passwords match
        if password != confirmpassword:
            messages.warning(request, "Passwords do not match")
            return redirect(reverse('signup'))
        
        # Check if username already exists
        if User.objects.filter(username=uname).exists():
            messages.info(request, "Username is already taken")
            return redirect(reverse('signup'))

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.info(request, "Email is already registered")
            return redirect(reverse('signup'))
        
        # Create new user
        user = User.objects.create_user(
            username=uname,
            first_name=firstname,
            last_name=lastname,
            email=email,
            password=password
        )
        user.is_active = False  # User is inactive until email is verified
        user.is_email_verified = False
        user.email_verification_token = uuid.uuid4()
        user.save()
        
        # Send verification email
        send_verification_email(user.email, str(user.email_verification_token))
        
        messages.success(request, "Signup successful! Please check your email to verify your account.")
        return redirect(reverse('login'))
    
    # Render the signup form if the request is not a POST
    return render(request, 'Users/signup.html')





@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def handlelogout(request):  
    request.session.clear()
    logout(request)
    return redirect('/')

def register_organization(request):
    if request.method == 'POST':
        org_email = request.POST['org_email']
        org_name = request.POST['org_name']
        org_regid = request.POST['org_regid']
        org_address = request.POST['org_address']
        org_phone = request.POST['org_phone']
        org_pincode = request.POST['org_pincode']
        org_pass1 = request.POST['org_pass1']
        org_pass2 = request.POST['org_pass2']
        
        # Check if passwords match
        if org_pass1 != org_pass2:
            messages.error(request, "Passwords do not match!")
            return redirect('org_signup')

        # Check if the organization registration ID or email already exists
        if Organizations.objects.filter(org_regid=org_regid).exists():
            messages.error(request, "Organization with this registration ID already exists!")
            return redirect('org_signup')
        
        if Organizations.objects.filter(org_email=org_email).exists():
            messages.error(request, "Organization with this email already exists!")
            return redirect('org_signup')

        # If validation passes, create the organization instance
        organization = Organizations(
            org_regid=org_regid,
            org_email=org_email,
            org_name=org_name,
            org_address=org_address,
            org_phone=org_phone,
            pincode=org_pincode,
            org_password=make_password(org_pass1),  # Hash the password
            approve=False,
            is_email_verified=False,
        )
        organization.save()
        
        # Send verification email
        send_verification_email(organization.org_email, str(organization.email_verification_token), is_organization=True)

        messages.success(request, "Organization registered successfully. Please check your email to verify your account.")
        return redirect('login')
    
    return render(request, 'Organizations/org_signup.html')

def org_logout(request):
    if 'org_id' in request.session:
        del request.session['org_id']
    if 'org_name' in request.session:
        del request.session['org_name']
    return redirect('org_login')  # Redirect to the login page after logout


def providers_list(request):
    return render(request, 'Organizations/providers_list.html')

user_pins={}

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
            # Generate a random 4-digit code
            code = random.randint(1000, 9999)
            user_pins[email] = code

            # Send email with the code
            send_mail(
                'Password Reset Code',
                f'Your password reset code is {code}.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            # Redirect to the verification page
            return redirect('verify_code', email=email)
        except User.DoesNotExist:
            messages.error(request, 'No user found with this email address.')
    return render(request, 'Forgot_Password/forgot_password.html')

# Verify code view
def verify_email(request, token, is_organization):
    try:
        if is_organization == '1':
            org = get_object_or_404(Organizations, email_verification_token=token)
            if not org.is_email_verified:
                org.is_email_verified = True
                org.save()
                messages.success(request, "Your organization email has been verified. Please wait for admin approval.")
            else:
                messages.info(request, "Your organization email has already been verified.")
        else:
            user = get_object_or_404(User, email_verification_token=token)
            if not user.is_email_verified:
                user.is_email_verified = True
                user.is_active = True
                user.save()
                messages.success(request, "Your email has been verified. You can now log in.")
            else:
                messages.info(request, "Your email has already been verified.")
    except Exception as e:
        messages.error(request, "Invalid verification link.")
    
    return redirect('login')

# Reset password view
def reset_password(request, email):
    User = get_user_model()
    if request.method == 'POST':
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if new_password1 and new_password2:
            if new_password1 == new_password2:
                try:
                    user = User.objects.get(email=email)
                    user.set_password(new_password1)
                    user.save()
                    messages.success(request, 'Password has been reset successfully.')
                    return redirect('login')
                except User.DoesNotExist:
                    messages.error(request, 'User with this email does not exist.')
            else:
                messages.error(request, 'Passwords do not match.')
        else:
            messages.error(request, 'Please provide both passwords.')

    return render(request, 'Forgot_Password/resetpassword.html', {'email': email})

# User = get_user_model()


def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = Staff.objects.filter(email=email).first()
        if user:
            token = get_random_string(32)
            user.password_reset_token = token
            user.save()
            
            reset_url = request.build_absolute_uri(reverse('password_reset_confirm', args=[token]))
            send_mail(
                'Password Reset Request',
                f'Click here to reset your password: {reset_url}',
                'from@example.com',
                [email],
                fail_silently=False,
            )
            return render(request, 'accounts/password_reset_sent.html')
    return render(request, 'accounts/password_reset_form.html')

def password_reset_confirm(request, token):
    user = Staff.objects.filter(password_reset_token=token).first()
    if user is None:
        return render(request, 'accounts/password_reset_invalid.html')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        user.set_password(new_password)
        user.password_reset_token = None
        user.save()
        return redirect('login')
    
    return render(request, 'accounts/password_reset_confirm.html')

def manage_users(request):
    users = User.objects.exclude(email="carefusion.ai@gmail.com")
    return render(request, 'Admin/manage_users.html', {'users': users})

def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.username = request.POST['username']
        user.email = request.POST['email']
        user.first_name = request.POST['first_name']
        user.last_name = request.POST['last_name']
        user.save()
        messages.success(request, 'User details updated successfully!')
        return redirect('manage_users')

    return render(request, 'Admin/edit_user.html', {'user': user})

def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully!')
        return redirect('manage_users')

    return render(request, 'Admin/delete_user.html', {'user': user})

def approve_organizations(request):
    unapproved_orgs = Organizations.objects.filter(approve=False)
    return render(request, 'Admin/approve_org.html', {'unapproved_orgs': unapproved_orgs})

@require_POST
def approve_request(request, request_id):
    if 'org_id' not in request.session:
        return JsonResponse({'success': False, 'message': 'Not authenticated'}, status=401)
    
    org_id = request.session['org_id']
    
    try:
        organization = Organizations.objects.get(id=org_id)
        service_request = get_object_or_404(ServiceRequest, id=request_id, organization=organization)
        service_request.status = 'APPROVED'
        service_request.save()
        return JsonResponse({'success': True, 'message': 'Service request approved successfully.'})
    except (Organizations.DoesNotExist, ServiceRequest.DoesNotExist) as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

# View for approving an organization
def approve_organization(request, org_id):
    if request.method == 'POST':
            org = Organizations.objects.get(id=org_id)
            if org:
                org.approve = True
                org.save()
    return redirect('approve_organizations')

def organization_detail(request, id):
    # Fetch the organization using the id parameter
    organization = Organizations.objects.get(org_regid=id)
    return render(request,'Users/organization_detail.html', {'organization': organization})


def submit_service_request(request, org_id):
    organization = get_object_or_404(Organizations, org_regid=org_id)

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST, request.FILES, organization=organization)
        if form.is_valid():
            try:
                service_request = form.save(commit=False)
                
                user_id = request.session.get('user_id')
                if user_id:
                    user = get_object_or_404(User, id=user_id)
                    service_request.patient = user
                else:
                    raise ValidationError('User is not authenticated.')
                
                service_request.organization = organization
                service_request.save()

                send_confirmation_email(user, organization, service_request)
                messages.success(request, 'Service request submitted successfully.')
                return redirect('patients_dashboard')
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = ServiceRequestForm(organization=organization)
    
    return render(request, 'Users/submit_service_request.html', {'form': form, 'organization': organization})


@require_POST
def handle_service_request(request):
    request_id = request.POST.get('request_id')
    action = request.POST.get('action')
    
    
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    patient = service_request.patient
    organization = service_request.organization
    current_time = timezone.now()

    if action == 'approve':
        service_request.status = 'approved'
        message = 'Service request approved successfully.'
        email_subject = 'Your Service Request has been Approved'
        email_message = f"""
        Dear {patient.get_full_name()},

        Your service request to {organization.org_name} has been approved.

        Request Details:
        - Request ID: {service_request.id}
        - Submitted on: {service_request.created_at}
        - Approved on: {current_time.strftime('%Y-%m-%d %H:%M:%S')}

        Please contact the organization for further details and next steps.

        Best regards,
        Care Fusion Team
        """
    elif action == 'reject':
        service_request.status = 'rejected'
        message = 'Service request rejected successfully.'
        email_subject = 'Your Service Request has been Rejected'
        email_message = f"""
        Dear {patient.get_full_name()},

        We regret to inform you that your service request to {organization.org_name} has been rejected.

        Request Details:
        - Request ID: {service_request.id}
        - Submitted on: {service_request.created_at}
        - Rejected on: {current_time.strftime('%Y-%m-%d %H:%M:%S')}

        If you have any questions, please contact the organization directly.

        Best regards,
        Care Fusion Team
        """
    else:
        messages.error(request, 'Invalid action.')
        return redirect('patient_details', request_id=request_id)
    
    service_request.save()

    # Send email to the patient
    send_mail(
        subject=email_subject,
        message=email_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[patient.email],
        fail_silently=False,
    )

    messages.success(request, message)
    return redirect('palliatives_dashboard')
    
    # try:
    #     service_request = ServiceRequest.objects.get(id=request_id)
    #     if action == 'approve':
    #         service_request.status = 'approved'
    #         message = 'Service request approved successfully.'
    #     elif action == 'reject':
    #         service_request.status = 'rejected'
    #         message = 'Service request rejected successfully.'
    #     else:
    #         return JsonResponse({'success': False, 'message': 'Invalid action.'})
        
    #     service_request.save()
    #     return JsonResponse({'success': True, 'message': message})
    # except ServiceRequest.DoesNotExist:
    #     return JsonResponse({'success': False, 'message': 'Service request not found.'})


def send_confirmation_email(user, organization, service_request):
    subject = f'Service Request Confirmation - {organization.org_name}'
    message = f"""
    Dear {user.get_full_name()},

    Your service request has been successfully submitted to {organization.org_name}.

    Request Details:
    - Request ID: {service_request.id}
    - Submitted on: {service_request.created_at}

    We will process your request and get back to you soon.

    Thank you for using our service.

    Best regards,
    Care Fusion Team
    """
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [user.email]
    
    try:
        with get_connection() as connection:
            email = EmailMessage(subject, message, from_email, recipient_list, connection=connection)
            email.send()
        logger.info(f"Confirmation email sent successfully to {user.email}")
    except SMTPServerDisconnected:
        logger.error(f"SMTP server disconnected. Email could not be sent to {user.email}")
    except Exception as e:
        logger.error(f"An error occurred while sending email to {user.email}: {str(e)}")
    
    
def user_notification_dashboard(request):
    user_id = request.session.get('user_id')
    if user_id:
        user = User.objects.get(id=user_id)
        service_requests = ServiceRequest.objects.filter(patient=user).order_by('-created_at')
        return render(request, 'Users/user_notification_dashboard.html', {'service_requests': service_requests})
    else:
        return JsonResponse({'success': False, 'message': 'User is not authenticated.'}, status=401)
    
    
# Staff details

def staff_list(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
        staff_members = Staff.objects.filter(organization=organization)
        context = {
            'organization': organization,
            'staff_members': staff_members,
        }
        return render(request, 'Organizations/staff_list.html', context)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')
    

def add_staff(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
        if request.method == 'POST':
            try:
                # Create staff instance from form data
                staff = Staff(
                    organization=organization,
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name'),
                    email=request.POST.get('email'),
                    phone=request.POST.get('phone'),  
                    role=request.POST.get('role'),
                    gender=request.POST.get('gender'),
                    address=request.POST.get('address'),
                    qualifications=request.POST.get('qualifications'),
                    is_active=False,  
                    username=request.POST.get('email')  
                )

                # Handle profile image
                if 'profile_image' in request.FILES:
                    staff.profile_image = request.FILES['profile_image']

                # Generate and set temporary password
                temp_password = get_random_string(12)
                staff.set_password(temp_password)
                
                # Save the staff member
                staff.save()

                # Generate confirmation token
                token = default_token_generator.make_token(staff)
                uid = urlsafe_base64_encode(force_bytes(staff.pk))
                
                # Prepare email content
                context = {
                    'staff_name': f"{staff.first_name} {staff.last_name}",
                    'organization_name': organization.org_name,
                    'confirmation_link': request.build_absolute_uri(
                        reverse('confirm_staff_email', args=[uid, token])
                    ),
                    'temp_password': temp_password,
                }
                html_message = render_to_string('Organizations/staff_confirmation_email.html', context)
                plain_message = strip_tags(html_message)
                
                # Send confirmation email
                send_mail(
                   'Confirm your staff account',
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [staff.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                messages.success(request, 'Staff added successfully. A confirmation email has been sent.')
                return redirect('staff_list')
                
            except Exception as e:
                messages.error(request, f'Error adding staff member: {str(e)}')
        
        return render(request, 'Organizations/add_staff.html', {'organization': organization})
        
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')
    
def confirm_staff_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        staff = Staff.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Staff.DoesNotExist):
        staff = None

    if staff is not None and default_token_generator.check_token(staff, token):
        if not staff.is_email_confirmed:
            staff.is_email_confirmed = True
            staff.is_active = True
            
            # Generate a temporary password
            temp_password = get_random_string(12)
            staff.set_password(temp_password)
            staff.must_change_password = True  # Set this to True
            staff.save()

            # Send login credentials email
            subject = 'Your Login Credentials'
            context = {
                'staff_name': f"{staff.first_name} {staff.last_name}",
                'email': staff.email,
                'temp_password': temp_password,
                'login_url': request.build_absolute_uri(reverse('login'))
            }
            html_message = render_to_string('staff/login_credentials_email.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [staff.email],
                html_message=html_message,
                fail_silently=False,
            )

            messages.success(request, 'Your email has been confirmed. Check your inbox for login credentials.')
        else:
            messages.info(request, 'Your email was already confirmed.')
    else:
        messages.error(request, 'The confirmation link was invalid or has expired.')

    return redirect('login')
    
@organization_login_required
def edit_staff(request, staff_id):
    org_id = request.session.get('org_id')
    organization = get_object_or_404(Organizations, id=org_id)
    staff = get_object_or_404(Staff, id=staff_id, organization=organization)

    if request.method == 'POST':
        try:
            # Get form data
            staff.first_name = request.POST.get('first_name')
            staff.last_name = request.POST.get('last_name')
            staff.email = request.POST.get('email')
            staff.phone = request.POST.get('phone')
            staff.gender = request.POST.get('gender')
            staff.role = request.POST.get('role')
            staff.experience = request.POST.get('experience')
            staff.address = request.POST.get('address')
            staff.qualifications = request.POST.get('qualifications')

            # Handle profile picture upload
            if request.FILES.get('profile_pic'):
                # Delete old profile picture if it exists
                if staff.profile_pic:
                    try:
                        staff.profile_pic.delete()
                    except Exception as e:
                        messages.warning(request, f"Could not delete old profile picture: {str(e)}")
                
                staff.profile_pic = request.FILES['profile_pic']

            # Validate email uniqueness
            if Staff.objects.exclude(id=staff_id).filter(email=staff.email).exists():
                messages.error(request, "This email is already registered with another staff member.")
                return redirect('edit_staff', staff_id=staff_id)

            # Validate phone number
            phone = staff.phone
            if not phone.isdigit() or len(phone) != 10 or not phone.startswith(('6', '7', '8', '9')):
                messages.error(request, "Please enter a valid 10-digit phone number starting with 6-9.")
                return redirect('edit_staff', staff_id=staff_id)

            # Validate experience
            try:
                experience = int(staff.experience)
                if experience < 0 or experience > 50:
                    raise ValueError
            except ValueError:
                messages.error(request, "Experience must be between 0 and 50 years.")
                return redirect('edit_staff', staff_id=staff_id)

            # Save the changes
            staff.save()
            messages.success(request, 'Staff member updated successfully.')
            return redirect('staff_list')

        except Exception as e:
            messages.error(request, f'Error updating staff member: {str(e)}')
            return redirect('edit_staff', staff_id=staff_id)

    context = {
        'staff': staff,
        'organization': organization
    }
    return render(request, 'Organizations/edit_staff.html', context)

@require_POST
def toggle_staff_status(request, staff_id):
    if 'org_id' not in request.session:
        return JsonResponse({
            'success': False,
            'message': "Please log in to access this page."
        })
    
    try:
        organization = Organizations.objects.get(id=request.session['org_id'])
        staff = get_object_or_404(Staff, id=staff_id, organization=organization)
        
        # Toggle the status
        staff.is_active = not staff.is_active
        staff.save()
        
        status = "enabled" if staff.is_active else "disabled"
        return JsonResponse({
            'success': True,
            'message': f'Staff member {staff.get_full_name()} has been {status}.',
            'is_active': staff.is_active
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

def get_staff_details(request):
    if 'org_id' not in request.session:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    staff_id = request.GET.get('staff_id')
    try:
        organization = Organizations.objects.get(id=request.session['org_id'])
        staff = get_object_or_404(Staff, id=staff_id, organization=organization)
        data = {
            'id': staff.id,
            'name': staff.name,
            'email': staff.email,
            'phone_number': staff.phone_number,
            'designation': staff.designation,
            'experience': staff.experience,
            'profile_pic': staff.profile_pic.url if staff.profile_pic else None,
        }
        return JsonResponse(data)
    except (Organizations.DoesNotExist, Staff.DoesNotExist) as e:
        return JsonResponse({'error': str(e)}, status=400)


def patient_assignment_list(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    org_name = request.session['org_name']
    
    try:
        organization = Organizations.objects.get(id=org_id, org_name=org_name)
        
        # Get assigned patients
        assigned_patients = PatientAssignment.objects.filter(
            organization=organization, 
            is_active=True
        ).select_related('patient', 'staff').order_by('-assigned_date')
        
        # Get unassigned patients
        assigned_patient_ids = assigned_patients.values_list('patient__id', flat=True)
        unassigned_patients = User.objects.filter(
            ~Q(id__in=assigned_patient_ids),
            is_superuser=False
        )
        
        # Pagination for assigned patients
        paginator = Paginator(assigned_patients, 10)  # Show 10 assignments per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'organization': organization,
            'page_obj': page_obj,
            'assigned_patients': page_obj,  # This is now paginated
            'unassigned_patients': unassigned_patients,
        }
        return render(request, 'Organizations/patient_assignment_list.html', context)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')
    
def unassign_patient(request, assignment_id):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    
    try:
        organization = Organizations.objects.get(id=org_id)
        assignment = get_object_or_404(PatientAssignment, id=assignment_id, organization=organization)
        assignment.is_active = False
        assignment.save()
        return redirect('patient_assignment_list')
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')

def assign_patient(request):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
        
        # Handle form submission
        if request.method == 'POST':
            patient_id = request.POST.get('patient')
            staff_id = request.POST.get('staff')
            
            if patient_id and staff_id:
                try:
                    # Create patient assignment
                    PatientAssignment.objects.create(
                        patient_id=patient_id,
                        staff_id=staff_id,
                        organization=organization,
                        is_active=True
                    )
                    messages.success(request, 'Patient successfully assigned to staff member.')
                    return redirect('patient_assignment_list')
                except Exception as e:
                    messages.error(request, f'Error assigning patient: {str(e)}')
            else:
                messages.error(request, 'Please select both patient and staff member.')
        
        # Get service requests for patients
        service_requests = ServiceRequest.objects.filter(
            organization=organization
        ).select_related('patient').distinct()
        
        # Get staff members
        staff_members = Staff.objects.filter(
            organization=organization,
            is_active=True
        )
        
        context = {
            'service_requests': service_requests,
            'staff_members': staff_members,
            'organization': organization
        }
        
        return render(request, 'Organizations/assign_patient.html', context)

    except Organizations.DoesNotExist:
        messages.error(request, 'Organization not found')
        return redirect('login')

# def unassign_patient(request, assignment_id):
#     if 'org_id' not in request.session:
#         messages.error(request, "Please log in to access this page.")
#         return redirect('login')
    
#     org_id = request.session['org_id']
    
#     try:
#         organization = Organizations.objects.get(id=org_id)
#         assignment = get_object_or_404(PatientAssignment, id=assignment_id, organization=organization)
#         assignment.is_active = False
#         assignment.save()
#         return redirect('patient_assignment_list')
#     except Organizations.DoesNotExist:
#         messages.error(request, "Organization not found. Please log in again.")
#         return redirect('login')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Staff, PatientAssignment, Prescription, Notification
from .forms import PrescriptionForm

def manage_prescriptions(request, assignment_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    assignment = get_object_or_404(PatientAssignment, id=assignment_id, staff=staff)
    prescriptions = Prescription.objects.filter(patient_assignment=assignment)

    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.patient_assignment = assignment
            prescription.save()

            # Attempt to create notification
            try:
                organization = staff.organization or assignment.organization or None
                Notification.objects.create(
                    patient=assignment.patient,
                    message=f"New prescription added: {prescription.medication}.",
                    organization=organization
                )
                messages.success(request, 'Prescription added successfully with notification.')
            except Exception as e:
                messages.warning(request, f'Prescription added, but notification creation failed: {str(e)}')

            return redirect('manage_prescriptions', assignment_id=assignment_id)
    else:
        form = PrescriptionForm()
    context = {
        'staff': staff,
        'assignment': assignment,
        'prescriptions': prescriptions,
        'form': form,
    }
    return render(request, 'staff/doctor/manage_prescriptions.html', context)

def edit_prescription(request, prescription_id):
    staff = get_object_or_404(Staff, user=request.user, role='DOCTOR')
    prescription = get_object_or_404(Prescription, id=prescription_id, patient_assignment__staff=staff)

    if request.method == 'POST':
        form = PrescriptionForm(request.POST, instance=prescription)
        if form.is_valid():
            form.save()
            messages.success(request, 'Prescription updated successfully.')
            return redirect('manage_prescriptions', assignment_id=prescription.patient_assignment.id)
    else:
        form = PrescriptionForm(instance=prescription)

    context = {
        'staff': staff,
        'prescription': prescription,
        'form': form,
    }
    return render(request, 'staff/doctor/edit_prescription.html', context)

def manage_all_appointments(request):
    appointments = Appointment.objects.filter(patient_assignment__staff=request.user)
    return render(request, 'staff/doctor/manage_all_appointments.html', {'appointments': appointments})

def manage_appointments(request, assignment_id=None):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    
    if assignment_id:
        assignment = get_object_or_404(PatientAssignment, id=assignment_id, staff=staff)
        upcoming_appointments = Appointment.objects.filter(
            patient_assignment_id=assignment_id,
            date_time__gte=timezone.now(),
            status='BOOKED'
        ).order_by('date_time')
    else:
        assignment = None
        upcoming_appointments = Appointment.objects.filter(
            patient_assignment__staff=staff,
            date_time__gte=timezone.now(),
            status='BOOKED'
        ).order_by('date_time')

    logger.debug(f"Number of upcoming appointments: {upcoming_appointments.count()}")
    for appointment in upcoming_appointments:
        logger.debug(f"Appointment: {appointment.date_time} - {appointment.purpose}")

    if request.method == 'POST':
        form = AppointmentForm(request.POST, is_staff=True)
        if form.is_valid():
            appointment = form.save(commit=False)
            if assignment:
                appointment.patient_assignment = assignment
            else:
                patient = form.cleaned_data['patient']
                assignment = PatientAssignment.objects.get(staff=staff, patient=patient)
                appointment.patient_assignment = assignment
            appointment.status = 'BOOKED'
            appointment.save()
            
            # Create a notification for the patient
            Notification.objects.create(
                patient=appointment.patient_assignment.patient,
                message=f"New appointment scheduled for {appointment.date_time.strftime('%B %d, %Y at %I:%M %p')}."
            )
            
            # Send email to patient
            send_appointment_email(appointment, 'scheduled', 'patient')
            
            # Send email to doctor
            send_appointment_email(appointment, 'scheduled', 'doctor')
            
            messages.success(request, 'Appointment scheduled successfully.')
            return redirect('manage_appointments', assignment_id=assignment_id)
    else:
        initial_datetime = timezone.now().replace(minute=0, second=0, microsecond=0) + timezone.timedelta(hours=1)
        form = AppointmentForm(is_staff=True, initial={
            'date': initial_datetime.date(),
            'time': initial_datetime.time()
        })

    context = {
        'staff': staff,
        'upcoming_appointments': upcoming_appointments,
        'form': form,
        'assignment': assignment,
    }
    return render(request, 'staff/doctor/manage_appointments.html', context)

def edit_appointment(request, appointment_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    appointment = get_object_or_404(Appointment, id=appointment_id, patient_assignment__staff=staff)

    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            form.save()
            
            # Create a notification for the patient
            Notification.objects.create(
                patient=appointment.patient_assignment.patient,
                message=f"Your appointment on {appointment.date_time.strftime('%B %d, %Y at %I:%M %p')} has been updated."
            )
            
            # Send email to patient
            send_appointment_email(appointment, 'updated')
            
            messages.success(request, 'Appointment updated successfully.')
            return redirect('manage_appointments', assignment_id=appointment.patient_assignment.id)
    else:
        form = AppointmentForm(instance=appointment)

    context = {
        'staff': staff,
        'appointment': appointment,
        'form': form,
    }
    return render(request, 'staff/doctor/edit_appointment.html', context)

def cancel_appointment(request, appointment_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    appointment = get_object_or_404(Appointment, id=appointment_id, patient_assignment__staff=staff)

    if request.method == 'POST':
        reason = request.POST.get('reason')
        appointment.status = 'CANCELLED'
        appointment.cancellation_reason = reason
        appointment.save()

        # Create a notification for the patient
        Notification.objects.create(
            patient=appointment.patient_assignment.patient,
            message=f"Your appointment on {appointment.date_time.strftime('%B %d, %Y at %I:%M %p')} has been cancelled."
        )

        # Send email to patient
        send_appointment_email(appointment, 'cancelled')

        messages.success(request, 'Appointment cancelled successfully.')
        return redirect('manage_all_appointments')

    context = {
        'staff': staff,
        'appointment': appointment,
    }
    return render(request, 'staff/doctor/cancel_appointment.html', context)

def manage_medical_history(request, assignment_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    assignment = get_object_or_404(PatientAssignment, id=assignment_id, staff=staff)

    if request.method == 'POST':
        entry = request.POST.get('entry')
        if entry:
            assignment.add_medical_history_entry(entry)
            messages.success(request, 'Medical history entry added successfully.')
        return redirect('manage_medical_history', assignment_id=assignment_id)

    context = {
        'staff': staff,
        'assignment': assignment,
    }
    return render(request, 'staff/doctor/manage_medical_history.html', context)

def notification_center(request):
    notifications = Notification.objects.filter(patient=request.user).order_by('-created_at')
    return render(request, 'notification_center.html', {'notifications': notifications})

# def messaging(request):
#     if request.method == 'POST':
#         recipient_id = request.POST.get('recipient')
#         content = request.POST.get('content')
#         recipient = get_object_or_404(User, id=recipient_id)
        
#         Message.objects.create(sender=request.user, recipient=recipient, content=content)
#         messages.success(request, 'Message sent successfully.')
        
#         # Create a notification for the recipient
#         Notification.objects.create(
#             patient=recipient,
#             message=f"New message from {request.user.get_full_name() or request.user.username}."
#         )
        
#         return redirect('messaging')

#     received_messages = Message.objects.filter(recipient=request.user).order_by('-timestamp')
#     sent_messages = Message.objects.filter(sender=request.user).order_by('-timestamp')
    
#     context = {
#         'received_messages': received_messages,
#         'sent_messages': sent_messages,
#     }
#     return render(request, 'messaging.html', context)


def messaging(request):
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        content = request.POST.get('content')
        try:
            recipient = get_object_or_404(User, id=recipient_id)
            Message.objects.create(sender=request.user, recipient=recipient, content=content)
            Notification.objects.create(
                patient=recipient,
                message=f"New message from {request.user.get_full_name() or request.user.username}."
            )
            return JsonResponse({
                'success': True,
                'message': 'Message sent successfully.',
                'redirect': reverse('messaging')
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error sending message: {str(e)}'
            })

    received_messages = Message.objects.filter(recipient=request.user).order_by('-timestamp')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-timestamp')
    return render(request, 'messaging.html', {
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    })

def schedule_appointment(request):
    # Check if user is logged in via session
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, 'You must be logged in to schedule an appointment.')
        return redirect('login')  # Redirect to your login page

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please log in again.')
        return redirect('login')

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            
            if user.is_staff:
                # If a staff member is scheduling
                patient_id = form.cleaned_data.get('patient')
                patient_assignment = PatientAssignment.objects.filter(
                    staff=user,
                    patient_id=patient_id
                ).first()
            else:
                # If a patient is scheduling
                patient_assignment = PatientAssignment.objects.filter(
                    patient_id=user.id
                ).first()
            
            if patient_assignment:
                appointment.patient_assignment = patient_assignment
                appointment.save()
                messages.success(request, 'Appointment scheduled successfully.')
                return redirect('manage_all_appointments')
            else:
                messages.error(request, 'No valid patient assignment found.')
        else:
            messages.error(request, 'There was an error in the form. Please check and try again.')
    else:
        form = AppointmentForm()
    
    context = {
        'form': form,
        'is_staff': user.is_staff
    }
    return render(request, 'schedule_appointment.html', context)

def available_appointments(request):
    if not request.session.get('username'):
        return redirect('login')
    
    user = User.objects.get(username=request.session['username'])
    assignments = PatientAssignment.objects.filter(patient=user, is_active=True)
    
    available_appointments = Appointment.objects.filter(
        patient_assignment__in=assignments,
        status='AVAILABLE',
        date_time__gte=timezone.now()
    ).order_by('date_time')
    
    booked_appointments = Appointment.objects.filter(
        patient_assignment__in=assignments,
        status='BOOKED',
        date_time__gte=timezone.now()
    ).order_by('date_time')
    
    return render(request, 'Users/available_appointments.html', {
        'available_appointments': available_appointments,
        'booked_appointments': booked_appointments,
    })
    
def book_appointment(request, appointment_id):
    if not request.session.get('username'):
        return redirect('login')
    
    user = User.objects.get(username=request.session['username'])
    appointment = get_object_or_404(Appointment, id=appointment_id, status='AVAILABLE')
    
    if appointment.patient_assignment.patient == user:
        appointment.status = 'BOOKED'
        appointment.save()
        
        # Create a notification for the doctor
        Notification.objects.create(
            staff=appointment.patient_assignment.staff,
            message=f"Patient {user.get_full_name()} has booked an appointment on {appointment.date_time.strftime('%B %d, %Y at %I:%M %p')}."
        )
        
        # Send email to doctor
        send_appointment_email(appointment, 'booked', recipient='doctor')
        
        messages.success(request, 'Appointment booked successfully!')
    else:
        messages.error(request, 'You are not authorized to book this appointment.')
    
    return redirect('available_appointments')

def batch_cancel_appointments(request):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')

    if request.method == 'POST':
        appointment_ids = request.POST.getlist('appointment_ids')
        reason = request.POST.get('reason')
        
        appointments = Appointment.objects.filter(id__in=appointment_ids, patient_assignment__staff=staff)
        for appointment in appointments:
            appointment.status = 'CANCELLED'
            appointment.cancellation_reason = reason
            appointment.save()

            # Create a notification for the patient
            Notification.objects.create(
                patient=appointment.patient_assignment.patient,
                message=f"Your appointment on {appointment.date_time.strftime('%B %d, %Y at %I:%M %p')} has been cancelled."
            )

            # Send email to patient
            send_appointment_email(appointment, 'cancelled')

        messages.success(request, f'{len(appointments)} appointments cancelled successfully.')
        return redirect('manage_all_appointments')

    appointments = Appointment.objects.filter(patient_assignment__staff=staff, status__in=['AVAILABLE', 'BOOKED'])
    context = {
        'staff': staff,
        'appointments': appointments,
    }
    return render(request, 'staff/doctor/batch_cancel_appointments.html', context)

def request_emergency_appointment(request):
    if not request.session.get('username'):
        return redirect('login')
    
    if request.method == 'POST':
        user = User.objects.get(username=request.session['username'])
        assignments = PatientAssignment.objects.filter(patient=user, is_active=True)
        
        for assignment in assignments:
            send_mail(
                'Emergency Appointment Request',
                f'Patient {user.get_full_name()} has requested an emergency appointment.',
                'from@example.com',
                [assignment.staff.email],
                fail_silently=False,
            )
        
        messages.success(request, 'Emergency appointment request sent to your assigned doctors.')
        return redirect('available_appointments')
    
    return render(request, 'Users/request_emergency_appointment.html')

# palliative organization team management

def team_list(request):
    org_id = request.session.get('org_id')
    if not org_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    organization = get_object_or_404(Organizations, id=org_id)
    teams = Team.objects.filter(organization=organization)
    
    context = {
        'organization': organization,
        'teams': teams,
    }
    return render(request, 'Organizations/team_list.html', context)


def generate_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))


@organization_login_required
def schedule_team_visit(request):
    organization = get_object_or_404(Organizations, id=request.session['org_id'])
    
    # Get current date and time
    today = date.today()
    current_time = datetime.now().strftime('%H:%M')
    
    # Get the team_id from query parameters
    selected_team = request.GET.get('team')
    
    # Get patients who have approved service requests for this organization
    approved_patients = User.objects.filter(
        servicerequest__organization=organization,
        servicerequest__status='approved'
    ).distinct()
    
    if request.method == 'POST':
        try:
            team = Team.objects.get(id=request.POST.get('team'), organization=organization)
            patient = User.objects.get(id=request.POST.get('patient'))
            
            # Verify patient has an approved service request
            if not ServiceRequest.objects.filter(
                organization=organization,
                patient=patient,
                status='approved'
            ).exists():
                messages.error(request, 'Selected patient does not have an approved service request.')
                return redirect('schedule_team_visit')
            
            # Check if the team is available on the scheduled date
            scheduled_date = datetime.strptime(request.POST.get('scheduled_date'), '%Y-%m-%d').date()
            schedule, created = TeamSchedule.objects.get_or_create(
                team=team,
                date=scheduled_date,
                defaults={'is_available': True}
            )
            
            if not schedule.is_available:
                messages.error(request, 'The selected team is not available on this date.')
                return redirect('schedule_team_visit')
            
            # Create the team visit
            visit = TeamVisit.objects.create(
                team=team,
                patient=patient,
                scheduled_date=scheduled_date,
                start_time=request.POST.get('start_time'),
                end_time=request.POST.get('end_time'),
                purpose=request.POST.get('purpose'),
                status='SCHEDULED'
            )
            
            messages.success(request, 'Team visit scheduled successfully.')
            return redirect('team_visit_list')
            
        except (Team.DoesNotExist, User.DoesNotExist) as e:
            messages.error(request, 'Invalid team or patient selected.')
        except Exception as e:
            messages.error(request, str(e))
    
    # Get all active teams for the organization
    teams = Team.objects.filter(organization=organization, is_active=True)
    
    context = {
        'teams': teams,
        'patients': approved_patients,
        'selected_team': selected_team,
        'today': today,
        'current_time': current_time,
    }
    
    return render(request, 'Organizations/schedule_team_visit.html', context)


def team_visit_list(request):
    org_id = request.session.get('org_id')
    if not org_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    organization = get_object_or_404(Organizations, id=org_id)
    team_visits = TeamVisit.objects.filter(team__organization=organization).order_by('scheduled_date', 'start_time')

    context = {
        'organization': organization,
        'team_visits': team_visits,
    }
    return render(request, 'Organizations/team_visit_list.html', context)

def team_visit_calendar(request):
    org_id = request.session.get('org_id')
    if not org_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    organization = get_object_or_404(Organizations, id=org_id)

    # Get the month and year from the query parameters, or use the current month
    month = int(request.GET.get('month', datetime.now().month))
    year = int(request.GET.get('year', datetime.now().year))

    # Get the first and last day of the month
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, monthrange(year, month)[1])

    # Fetch team visits for the selected month
    team_visits = TeamVisit.objects.filter(
        team__organization=organization,
        scheduled_date__range=[first_day, last_day]
    ).select_related('team', 'patient')

    # Create a calendar matrix
    calendar_matrix = []
    current_date = first_day
    while current_date.month == month:
        week = []
        for _ in range(7):
            if current_date.month == month:
                day_visits = [visit for visit in team_visits if visit.scheduled_date == current_date.date()]
                week.append((current_date.day, day_visits))
            else:
                week.append((None, []))
            current_date += timedelta(days=1)
        calendar_matrix.append(week)

    context = {
        'calendar_matrix': calendar_matrix,
        'month': first_day,
        'prev_month': (first_day - timedelta(days=1)).replace(day=1),
        'next_month': (last_day + timedelta(days=1)).replace(day=1),
    }

    return render(request, 'Organizations/team_visit_calendar.html', context)

def reschedule_team_visit(request, visit_id):
    org_id = request.session.get('org_id')
    if not org_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    organization = get_object_or_404(Organizations, id=org_id)
    visit = get_object_or_404(TeamVisit, id=visit_id, team__organization=organization)
    
    if not visit.is_reschedulable():
        messages.error(request, "This visit cannot be rescheduled.")
        return redirect('team_visit_calendar')

    if request.method == 'POST':
        form = RescheduleTeamVisitForm(request.POST)
        if form.is_valid():
            try:
                new_visit = visit.reschedule(
                    form.cleaned_data['new_date'],
                    form.cleaned_data['new_start_time'],
                    form.cleaned_data['new_end_time'],
                    form.cleaned_data['reason']
                )
                
                # Create notifications for team members and patient
                notification_message = f"Team visit rescheduled from {visit.scheduled_date} to {new_visit.scheduled_date}"
                for staff in new_visit.team.members.all():
                    Notification.objects.create(
                        staff=staff,
                        message=notification_message,
                        organization=organization
                    )
                
                # Create notification for the patient
                Notification.objects.create(
                    patient=new_visit.patient,
                    message=notification_message,
                    organization=organization
                )
                
                messages.success(request, "Visit rescheduled successfully.")
                return redirect('team_visit_calendar')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = RescheduleTeamVisitForm(initial={
            'new_date': visit.scheduled_date,
            'new_start_time': visit.start_time,
            'new_end_time': visit.end_time,
        })

    context = {
        'form': form,
        'visit': visit,
    }
    return render(request, 'Organizations/reschedule_team_visit.html', context)

@require_GET
def get_available_slots(request, team_id, date):
    team = get_object_or_404(Team, id=team_id)
    date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    
    # Define your working hours and slot duration
    start_hour, start_minute = 9, 0
    end_hour, end_minute = 17, 0
    slot_duration = timedelta(minutes=30)
    
    available_slots = []
    current_slot = datetime.combine(date_obj, time(start_hour, start_minute))
    end_time = datetime.combine(date_obj, time(end_hour, end_minute))
    
    while current_slot < end_time:
        slot_end = current_slot + slot_duration
        if not TeamVisit.check_conflicts(team, date_obj, current_slot.time(), slot_end.time()):
            available_slots.append(current_slot.strftime('%H:%M'))
        current_slot = slot_end
    
    return JsonResponse({'available_slots': available_slots})

def team_communication(request, team_id):
    role = request.session.get('role')
    org_id = request.session.get('org_id')

    if not role or not org_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    organization = get_object_or_404(Organizations, id=org_id)
    team = get_object_or_404(Team, id=team_id, organization=organization)

    if role == 'staff':
        staff_id = request.session.get('staff_id')
        if not staff_id:
            messages.error(request, "Staff information not found. Please log in again.")
            return redirect('login')

        staff = get_object_or_404(Staff, id=staff_id)
        if staff not in team.members.all():
            messages.error(request, "You are not a member of this team.")
            return redirect('team_list')

        sender_id = staff_id
        sender_type = 'staff'
    elif role == 'organization':
        sender_id = org_id
        sender_type = 'organization'
    else:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')

    team_messages = TeamMessage.objects.filter(team=team)

    context = {
        'team': team,
        'team_messages': team_messages,
        'sender_id': sender_id,
        'sender_type': sender_type,
    }
    return render(request, 'Organizations/team_communication.html', context)

def visit_checklist_notes(request, visit_id):
    org_id = request.session.get('org_id')
    if not org_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    organization = get_object_or_404(Organizations, id=org_id)
    visit = get_object_or_404(TeamVisit, id=visit_id, team__organization=organization)
    staff = get_object_or_404(Staff, id=request.session.get('staff_id'))

    checklist, created = VisitChecklist.objects.get_or_create(team_visit=visit)

    if request.method == 'POST':
        checklist_form = VisitChecklistForm(request.POST, instance=checklist)
        note_form = VisitNoteForm(request.POST)
        if checklist_form.is_valid() and note_form.is_valid():
            checklist_form.save()
            note = note_form.save(commit=False)
            note.team_visit = visit
            note.staff = staff
            note.save()
            messages.success(request, "Checklist and note updated successfully.")
            return redirect('visit_checklist_notes', visit_id=visit_id)
    else:
        checklist_form = VisitChecklistForm(instance=checklist)
        note_form = VisitNoteForm()

    notes = VisitNote.objects.filter(team_visit=visit)

    context = {
        'visit': visit,
        'checklist_form': checklist_form,
        'note_form': note_form,
        'notes': notes,
    }
    return render(request, 'Organizations/visit_checklist_notes.html', context)

class TeamListView(ListView):
    model = Team
    template_name = 'Organizations/team_list.html'
    context_object_name = 'teams'

    def get_queryset(self):
        org_id = self.request.session.get('org_id')
        return Team.objects.filter(organization_id=org_id)

# realtime team communication

def generate_credentials():
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=12))
    return username, password


def team_dashboard(request):
    staff = Staff.objects.get(id=request.session['staff_id'])
    team_memberships = TeamDashboard.objects.filter(staff=staff)
    
    context = {
        'staff': staff,
        'team_memberships': team_memberships
    }
    
    return render(request, 'staff/team_dashboard.html', context)

def get_team_messages(request, team_id):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    staff = get_object_or_404(Staff, id=staff_id)
    team = get_object_or_404(Team, id=team_id)
    
    if staff not in team.members.all():
        return JsonResponse({'error': 'Not a member of this team'}, status=403)
    
    messages = TeamMessage.objects.filter(team=team).order_by('created_at')
    message_data = [
        {
            'sender_name': msg.sender.get_full_name() if msg.sender else msg.organization.org_name,
            'content': msg.content,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        for msg in messages
    ]
    
    return JsonResponse({'messages': message_data})

@staff_login_required
def team_dashboard_change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        try:
            team_dashboard = TeamDashboard.objects.get(username=request.user.email)
        except TeamDashboard.DoesNotExist:
            messages.error(request, "You don't have access to the team dashboard.")
            return redirect('some_appropriate_page')  # Redirect to an appropriate page

        if not check_password(current_password, team_dashboard.password):
            messages.error(request, "Current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        else:
            team_dashboard.password = make_password(new_password)
            team_dashboard.save()
            messages.success(request, "Team dashboard password changed successfully.")
            return redirect('team_dashboard')  # Redirect to the team dashboard page

    return render(request, 'Organizations/team_dashboard_change_password.html')

def team_dashboard_change_password(request):
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')  # Redirect to your login page

    try:
        staff = get_object_or_404(Staff, id=staff_id)
        team_dashboard = TeamDashboard.objects.get(username=staff.email)
    except TeamDashboard.DoesNotExist:
        messages.error(request, "You don't have access to the team dashboard.")
        return redirect('some_appropriate_page')  # Redirect to an appropriate page

    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not check_password(current_password, team_dashboard.password):
            messages.error(request, "Current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        else:
            team_dashboard.password = make_password(new_password)
            team_dashboard.save()
            messages.success(request, "Team dashboard password changed successfully.")
            return redirect('team_dashboard')  # Redirect to the team dashboard page

    return render(request, 'Organizations/team_dashboard_change_password.html')


def team_detail(request, team_id):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    team = get_object_or_404(Team, id=team_id)
    patient = get_object_or_404(User, id=request.session['user_id'])

    # Check if the patient is assigned to the organization of this team
    if not PatientAssignment.objects.filter(
        patient=patient, 
        organization=team.organization, 
        is_active=True
    ).exists():
        messages.error(request, "You don't have access to this team's information.")
        return redirect('patients_dashboard')

    context = {
        'team': team,
        'team_members': team.members.all(),
        'organization': team.organization,
    }
    return render(request, 'Users/team_detail.html', context)

def request_appointment(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    user = get_object_or_404(User, id=request.session['user_id'])

    try:
        patient_assignment = PatientAssignment.objects.get(patient=user)
    except PatientAssignment.DoesNotExist:
        messages.error(request, "You are not assigned to any staff member. Please contact support.")
        return redirect('patients_dashboard')

    if request.method == 'POST':
        form = AppointmentRequestForm(request.POST)
        if form.is_valid():
            appointment_request = form.save(commit=False)
            appointment_request.patient_assignment = patient_assignment
            appointment_request.status = 'BOOKED'  # or 'AVAILABLE', depending on your workflow
            appointment_request.save()
            messages.success(request, "Appointment request submitted successfully.")
            return redirect('patients_dashboard')
    else:
        form = AppointmentRequestForm()

    return render(request, 'Users/request_appointment.html', {'form': form})

from django.utils import timezone

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def assigned_teams(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    patient = get_object_or_404(User, id=request.session['user_id'])
    
    # Get teams using the same logic as in patients_dashboard
    teams = Team.objects.filter(
        organization__patient_assignments__patient=patient,
        organization__patient_assignments__is_active=True,
        is_active=True
    ).distinct().prefetch_related(
        'members',
        'visits'
    )

    today = timezone.now().date()

    context = {
        'teams': teams,
        'patient': patient,
        'today': today,
        'notifications': Notification.objects.filter(patient=patient, is_read=False)
    }
    
    return render(request, 'Users/assigned_teams.html', context)
    
    return render(request, 'Users/assigned_teams.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def request_team_visit(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    patient = get_object_or_404(User, id=request.session['user_id'])
    
    # Get teams from organizations where the patient has assignments
    assigned_teams = Team.objects.filter(
        organization__patient_assignments__patient=patient,
        organization__patient_assignments__is_active=True,
        is_active=True
    ).distinct()

    if request.method == 'POST':
        try:
            team = get_object_or_404(Team, id=request.POST.get('team'))
            preferred_date = datetime.strptime(request.POST.get('preferred_date'), '%Y-%m-%d').date()
            preferred_time = request.POST.get('preferred_time')
            reason = request.POST.get('reason')
            notes = request.POST.get('notes', '')

            # Create team visit request
            TeamVisitRequest.objects.create(
                patient=patient,
                team=team,
                requested_date=preferred_date,
                purpose=preferred_time,  # Using purpose field for time preference
                reason=reason,
                status='PENDING'
            )

            messages.success(request, "Team visit request submitted successfully!")
            return redirect('upcoming_team_visits')

        except Exception as e:
            messages.error(request, f"Error submitting request: {str(e)}")

    # Calculate min and max dates for date picker
    min_date = timezone.now().date() + timedelta(days=1)  # Tomorrow
    max_date = min_date + timedelta(days=30)  # Up to 30 days in advance

    context = {
        'assigned_teams': assigned_teams,
        'min_date': min_date,
        'max_date': max_date,
        'patient': patient,
    }
    
    return render(request, 'Users/request_team_visit.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def request_team_visit_specific(request, team_id):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    patient = get_object_or_404(User, id=request.session['user_id'])
    team = get_object_or_404(Team, id=team_id)
    
    # Verify that the patient is assigned to this team
    if not PatientAssignment.objects.filter(
        patient=patient,
        team=team,
        is_active=True
    ).exists():
        messages.error(request, "You are not assigned to this team.")
        return redirect('patients_dashboard')

    if request.method == 'POST':
        try:
            preferred_date = datetime.strptime(request.POST.get('preferred_date'), '%Y-%m-%d').date()
            preferred_time = request.POST.get('preferred_time')
            reason = request.POST.get('reason')
            notes = request.POST.get('notes', '')

            # Create team visit request
            TeamVisitRequest.objects.create(
                patient=patient,
                team=team,
                preferred_date=preferred_date,
                preferred_time=preferred_time,
                reason=reason,
                additional_notes=notes,
                status='PENDING'
            )

            messages.success(request, "Team visit request submitted successfully!")
            return redirect('upcoming_team_visits')

        except Exception as e:
            messages.error(request, f"Error submitting request: {str(e)}")

    # Calculate min and max dates for date picker
    min_date = timezone.now().date() + timedelta(days=1)
    max_date = min_date + timedelta(days=30)

    context = {
        'team': team,
        'min_date': min_date,
        'max_date': max_date,
        'patient': patient,
    }
    
    return render(request, 'Users/request_team_visit.html', context)

def patient_visit_requests(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    patient = get_object_or_404(User, id=request.session['user_id'])
    visit_requests = TeamVisitRequest.objects.filter(patient=patient).order_by('-created_at')

    context = {
        'visit_requests': visit_requests,
    }
    return render(request, 'Users/patient_visit_requests.html', context)

def patient_notifications(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    patient = get_object_or_404(User, id=request.session['user_id'])
    notifications = Notification.objects.filter(patient=patient).order_by('-created_at')

    context = {
        'notifications': notifications,
    }
    return render(request, 'Users/patient_notifications.html', context)

def notification_center(request):
    # Implement logic to display all notifications
    pass

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def patient_profile(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    user_id = request.session['user_id']
    patient = get_object_or_404(User, id=user_id)
    
    # Check if user is authenticated via social auth (Google)
    is_social_auth = patient.social_auth.filter(provider='google-oauth2').exists() if hasattr(patient, 'social_auth') else False
    
    # If user is authenticated via Google, ensure email is marked as verified
    if is_social_auth and not patient.is_email_verified:
        patient.is_email_verified = True
        patient.save()
    
    # Get pending requests count for the notification badge
    pending_requests_count = ServiceRequest.objects.filter(
        patient=patient,
        status='PENDING'
    ).count()

    context = {
        'patient': patient,
        'pending_requests_count': pending_requests_count,
        'is_social_auth': is_social_auth
    }
    
    return render(request, 'Users/patient_profile.html', context)

def org_profile(request):
    # Implement logic to display and edit organization profile
    pass

# def manage_organizations(request):
#     if not request.session.get('user_id') or request.session.get('role') != 'admin':
#         messages.error(request, "Please login as admin to access this page.")
#         return redirect('login')
        
#     # Get all organizations that are both approved and email verified
#     organizations = Organizations.objects.filter(
#         approve=True,
#         is_email_verified=True
#     ).order_by('org_name')
    
#     context = {
#         'organizations': organizations,
#         'total_organizations': organizations.count()
#     }
#     return render(request, 'Admin/manage_organizations.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_organization(request, org_id):
    if not request.session.get('user_id') or request.session.get('role') != 'admin':
        messages.error(request, "Please login as admin to access this page.")
        return redirect('login')
    
    organization = get_object_or_404(Organizations, id=org_id)
    
    if request.method == 'POST':
        # Update organization details
        organization.org_name = request.POST['org_name']
        organization.org_email = request.POST['org_email']
        organization.org_regid = request.POST['org_regid']
        organization.org_phone = request.POST['org_phone']
        organization.org_address = request.POST['org_address']
        organization.pincode = request.POST['pincode']
        
        try:
            organization.save()
            messages.success(request, 'Organization updated successfully!')
            return redirect('manage_organizations')
        except Exception as e:
            messages.error(request, f'Error updating organization: {str(e)}')
    
    return render(request, 'Admin/edit_organization.html', {'organization': organization})

@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def toggle_organization_status(request, org_id):
    if not request.session.get('user_id') or request.session.get('role') != 'admin':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')
    
    try:
        organization = Organizations.objects.get(id=org_id)
        organization.approve = not organization.approve
        organization.save()
        
        status = "enabled" if organization.approve else "disabled"
        messages.success(request, f"Organization has been {status} successfully!")
        return redirect('admin_dashboard')
        
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found.")
        return redirect('admin_dashboard')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('admin_dashboard')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def patient_service_requests(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    user_id = request.session['user_id']
    patient = get_object_or_404(User, id=user_id)
    
    # Get all service requests for the patient, ordered by most recent first
    service_requests = ServiceRequest.objects.filter(
        patient=patient
    ).select_related(
        'organization',
        'service'
    ).order_by('-created_at')

    context = {
        'service_requests': service_requests,
        'patient': patient,
    }

    return render(request, 'Users/patient_service_requests.html', context)

def get_services(request, org_id):
    organization = get_object_or_404(Organizations, id=org_id)
    services = Service.objects.filter(organization=organization)
    services_data = [{'id': service.id, 'name': service.name} for service in services]
    return JsonResponse({'services': services_data})

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def update_profile(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    user_id = request.session['user_id']
    patient = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('patient_profile')
    else:
        form = ProfileUpdateForm(instance=patient)

    context = {
        'form': form,
        'patient': patient
    }

    return render(request, 'Users/update_profile.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def patient_settings(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    user_id = request.session['user_id']
    patient = get_object_or_404(User, id=user_id)

    context = {
        'patient': patient,
    }
    
    return render(request, 'Users/patient_settings.html', context)

@require_POST
def change_password(request):
    if not request.session.get('user_id'):
        return JsonResponse({'status': 'error', 'message': 'Not authenticated'})

    current_password = request.POST.get('current_password')
    new_password = request.POST.get('new_password')
    confirm_password = request.POST.get('confirm_password')

    user = get_object_or_404(User, id=request.session['user_id'])

    if not user.check_password(current_password):
        messages.error(request, 'Current password is incorrect.')
        return redirect('patient_settings')

    if new_password != confirm_password:
        messages.error(request, 'New passwords do not match.')
        return redirect('patient_settings')

    user.set_password(new_password)
    user.save()
    messages.success(request, 'Password changed successfully.')
    return redirect('patient_settings')

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import User, NotificationPreferences

@require_POST
def update_notification_preferences(request):
    if not request.session.get('user_id'):
        return JsonResponse({'status': 'error', 'message': 'Not authenticated'})

    user = get_object_or_404(User, id=request.session['user_id'])
    
    # Get or create notification preferences
    notification_prefs, created = NotificationPreferences.objects.get_or_create(
        user=user,
        defaults={
            'email_enabled': False,
            'appointment_reminders': False
        }
    )
    
    # Update the preferences
    notification_prefs.email_enabled = 'email_notifications' in request.POST
    notification_prefs.appointment_reminders = 'appointment_reminders' in request.POST
    notification_prefs.save()
    
    messages.success(request, 'Notification preferences updated successfully.')
    return redirect('patient_settings')

@require_POST
def update_privacy_settings(request):
    if not request.session.get('user_id'):
        return JsonResponse({'status': 'error', 'message': 'Not authenticated'})

    user = get_object_or_404(User, id=request.session['user_id'])
    
    # Get or create privacy settings
    privacy_settings, created = PrivacySettings.objects.get_or_create(
        user=user,
        defaults={
            'profile_visible': False
        }
    )
    
    # Update the settings
    privacy_settings.profile_visible = 'profile_visible' in request.POST
    privacy_settings.save()
    
    messages.success(request, 'Privacy settings updated successfully.')
    return redirect('patient_settings')

@require_POST
def deactivate_account(request):
    if not request.session.get('user_id'):
        return JsonResponse({'status': 'error', 'message': 'Not authenticated'})

    confirmation = request.POST.get('confirm_deactivation')
    if confirmation != 'DEACTIVATE':
        messages.error(request, 'Please type DEACTIVATE to confirm account deactivation.')
        return redirect('patient_settings')

    user = get_object_or_404(User, id=request.session['user_id'])
    user.is_active = False
    user.save()
    
    logout(request)
    messages.success(request, 'Your account has been deactivated.')
    return redirect('login')


@organization_login_required
def create_team(request):
    org_id = request.session.get('org_id')
    organization = get_object_or_404(Organizations, id=org_id)

    if request.method == 'POST':
        team_name = request.POST.get('name')
        member_ids = request.POST.getlist('members')
        
        # Basic validation
        if not team_name or len(member_ids) < 2:
            if not team_name:
                messages.error(request, "Team name is required.")
            if len(member_ids) < 2:
                messages.error(request, "Please select at least 2 team members.")
            return redirect('create_team')

        try:
            # Get selected members
            selected_members = Staff.objects.filter(id__in=member_ids)
            existing_team_members = []
            
            # Check if members are already in teams
            for member in selected_members:
                existing_team = TeamDashboard.objects.filter(staff=member).first()
                if existing_team:
                    existing_team_members.append({
                        'name': member.get_full_name(),
                        'team': existing_team.team.name
                    })

            # If any member is already in a team, show error and redirect
            if existing_team_members:
                for member in existing_team_members:
                    messages.warning(
                        request,
                        f"{member['name']} is already a member of team '{member['team']}'.",
                        extra_tags='dismissible'
                    )
                return redirect('team_list')

            # Create the team
            team = Team.objects.create(
                name=team_name,
                organization=organization
            )
            team.members.set(selected_members)

            # Create team dashboards for all members without login credentials
            success_count = 0
            for member in team.members.all():
                try:
                    TeamDashboard.objects.create(
                        team=team,
                        staff=member,
                        role='MEMBER'
                    )
                    success_count += 1
                except Exception as e:
                    messages.error(
                        request,
                        f"Failed to add {member.get_full_name()} to team dashboard: {str(e)}",
                        extra_tags='dismissible'
                    )

            if success_count > 0:
                messages.success(request, f'Team created successfully with {success_count} member(s).')
            return redirect('team_list')

        except Exception as e:
            messages.error(request, f"Error creating team: {str(e)}")
            return redirect('create_team')

    # Get available staff for the organization
    available_staff = Staff.objects.filter(
        organization=organization,
        is_active=True
    ).order_by('first_name', 'last_name')

    context = {
        'available_staff': available_staff,
        'organization': organization,
    }
    return render(request, 'Organizations/create_team.html', context)

def generate_password():
    """Generate a random password for team dashboard"""
    length = 12
    characters = string.ascii_letters + string.digits + string.punctuation
    while True:
        password = ''.join(random.choice(characters) for i in range(length))
        # Check if password has at least one number and one special character
        if (any(c.isdigit() for c in password) and 
            any(c in string.punctuation for c in password) and
            any(c.isupper() for c in password) and
            any(c.islower() for c in password)):
            return password

@organization_login_required
def edit_team(request, team_id):
    org_id = request.session.get('org_id')
    organization = get_object_or_404(Organizations, id=org_id)
    team = get_object_or_404(Team, id=team_id, organization=organization)
    
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team, organization=organization)
        if form.is_valid():
            # Get the original members before updating
            original_members = set(team.members.all())
            
            # Save the team with new data
            team = form.save()
            
            # Get the new members after updating
            new_members = set(team.members.all())
            
            # Handle removed members
            removed_members = original_members - new_members
            for member in removed_members:
                TeamDashboard.objects.filter(team=team, staff=member).delete()
            
            # Handle new members
            added_members = new_members - original_members
            for member in added_members:
                try:
                    # Check if member already has a TeamDashboard
                    existing_dashboard = TeamDashboard.objects.filter(username=member.email).first()
                    if existing_dashboard:
                        messages.warning(
                            request,
                            f"{member.get_full_name()} is already a member of team '{existing_dashboard.team.name}'.",
                            extra_tags='dismissible'
                        )
                        team.members.remove(member)
                        continue

                    password = generate_password()
                    TeamDashboard.objects.create(
                        team=team,
                        staff=member,
                        username=member.email,
                        password=make_password(password)
                    )
                    # Send email with credentials
                    send_mail(
                        'Team Dashboard Credentials',
                        f'Your team dashboard username: {member.email}\nPassword: {password}',
                        settings.DEFAULT_FROM_EMAIL,
                        [member.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    messages.error(
                        request,
                        f"Failed to add {member.get_full_name()}: {str(e)}",
                        extra_tags='dismissible'
                    )
                    team.members.remove(member)
            
            messages.success(request, 'Team updated successfully.')
            return redirect('team_list')
    else:
        form = TeamForm(instance=team, organization=organization)
    
    return render(request, 'Organizations/edit_team.html', {
        'form': form,
        'team': team,
        'organization': organization
    })

@organization_login_required
def toggle_team_status(request, team_id):
    if request.method == 'POST':
        org_id = request.session.get('org_id')
        organization = get_object_or_404(Organizations, id=org_id)
        team = get_object_or_404(Team, id=team_id, organization=organization)
        
        # Add is_active field to Team model if not exists
        team.is_active = not team.is_active
        team.save()
        
        status = "enabled" if team.is_active else "disabled"
        messages.success(request, f'Team {team.name} has been {status}.')
        
        # Return JSON response for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'is_active': team.is_active,
                'message': f'Team {team.name} has been {status}.'
            })
            
        return redirect('team_list')
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@organization_login_required
def edit_team_visit(request, visit_id):
    team_visit = get_object_or_404(TeamVisit, 
                                  id=visit_id, 
                                  team__organization_id=request.session.get('org_id'))
    
    if request.method == 'POST':
        try:
            team_visit.scheduled_date = request.POST.get('scheduled_date')
            team_visit.start_time = request.POST.get('start_time')
            team_visit.end_time = request.POST.get('end_time')
            team_visit.purpose = request.POST.get('purpose')
            team_visit.status = request.POST.get('status')
            team_visit.save()
            
            messages.success(request, 'Team visit updated successfully.')
            return redirect('team_visit_list')
            
        except Exception as e:
            messages.error(request, f'Error updating team visit: {str(e)}')
            return redirect('team_visit_list')
    
    context = {
        'team_visit': team_visit,
        'today': date.today(),
        'visit_id': visit_id
    }
    
    return render(request, 'Organizations/edit_team_visit.html', context)

@organization_login_required
def cancel_team_visit(request, visit_id):
    try:
        visit = get_object_or_404(TeamVisit, 
                                 id=visit_id,
                                 team__organization_id=request.session.get('org_id'))
        visit.status = 'CANCELLED'
        visit.save()
        messages.success(request, 'Team visit cancelled successfully.')
    except Exception as e:
        messages.error(request, f'Error cancelling team visit: {str(e)}')
    
    return redirect('team_visit_list')

def cancel_team_visit(request, visit_id):
    # Check if user is logged in via session
    if 'org_name' not in request.session:
        messages.error(request, 'Please login to access this page.')
        return redirect('login')

    visit = get_object_or_404(TeamVisit, id=visit_id)
    
    # Check if the visit's team belongs to the logged-in organization
    if str(visit.team.organization.id) != str(request.session.get('org_id')):
        messages.error(request, 'You do not have permission to cancel this visit.')
        return redirect('team_visit_list')

    visit.status = 'CANCELLED'
    visit.save()
    messages.success(request, 'Team visit cancelled successfully.')
    return redirect('team_visit_list')

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_taxi_drivers(request):
    if not request.session.get('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    organization = get_object_or_404(Organizations, id=request.session['org_id'])
    
    if request.method == 'POST':
        try:
            # Create TaxiDriver directly
            driver = TaxiDriver(
                email=request.POST.get('email'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                organization=organization,
                vehicle_number=request.POST.get('vehicle_number'),
                vehicle_type=request.POST.get('vehicle_type'),
                license_number=request.POST.get('license_number'),
                verification_token=get_random_string(64)
            )
            driver.save()

            # Send verification email
            verification_url = request.build_absolute_uri(
                reverse('verify_driver_email', args=[driver.verification_token])
            )
            
            send_mail(
                'Verify Your Email',
                f'Click here to verify your email: {verification_url}',
                settings.DEFAULT_FROM_EMAIL,
                [driver.email],
                fail_silently=False,
            )
            
            messages.success(request, "Driver added! Verification email sent.")
            return redirect('manage_taxi_drivers')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    drivers = TaxiDriver.objects.filter(organization=organization)
    context = {
        'drivers': drivers,
        'organization': organization,
        'vehicle_types': TaxiDriver.VEHICLE_TYPES
    }
    
    return render(request, 'Organizations/manage_taxi_drivers.html', context)

def verify_driver_email(request, token):
    driver = get_object_or_404(TaxiDriver, verification_token=token)
    if not driver.email_verified:
        # Generate and hash new password
        password = get_random_string(8)
        driver.password = make_password(password)
        driver.email_verified = True
        driver.verification_token = None
        driver.save()

        # Send password email
        send_mail(
            'Your Login Credentials',
            f'''Hello {driver.first_name},
            
Your email has been verified successfully!
Your login credentials are:
Email: {driver.email}
Password: {password}

Please change your password after logging in.''',
            settings.DEFAULT_FROM_EMAIL,
            [driver.email],
            fail_silently=False,
        )
        
        messages.success(request, "Email verified! Password sent to your email.")
    else:
        messages.info(request, "Email already verified.")
    
    return redirect('login')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def request_emergency_taxi(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    patient = get_object_or_404(User, id=request.session['user_id'])
    
    # Check eligibility
    has_approved_requests = ServiceRequest.objects.filter(
        patient=patient,
        status='APPROVED'
    ).exists()
    
    if not has_approved_requests:
        messages.error(request, "You are not eligible to use this service. Please contact your organization.")
        return redirect('patients_dashboard')
    
    if request.method == 'POST':
        form = TaxiBookingForm(request.POST)
        if form.is_valid():
            organization_id = request.POST.get('organization')
            organization = get_object_or_404(Organizations, id=organization_id)
            
            # Calculate distance and fare
            distance = calculate_distance(
                form.cleaned_data['pickup_latitude'],
                form.cleaned_data['pickup_longitude'],
                form.cleaned_data['drop_latitude'],
                form.cleaned_data['drop_longitude']
            )
            
            estimated_fare = calculate_fare(organization, distance)
            
            # Create booking
            booking = form.save(commit=False)
            booking.patient = patient
            booking.organization = organization
            booking.distance_km = distance
            booking.estimated_fare = estimated_fare
            booking.save()
            
            # Create Razorpay order
            order = create_razorpay_order(estimated_fare)
            
            return JsonResponse({
                'order_id': order.id,
                'amount': estimated_fare,
                'booking_id': booking.id
            })
    else:
        form = TaxiBookingForm()
    
    organizations = Organizations.objects.filter(
        service_requests__patient=patient,
        service_requests__status='APPROVED'
    ).distinct()
    
    context = {
        'form': form,
        'organizations': organizations,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID
    }
    
    return render(request, 'Users/request_emergency_taxi.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def approve_taxi_request(request, booking_id):
    if not request.session.get('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    booking = get_object_or_404(TaxiBooking, id=booking_id)
    
    if request.method == 'POST':
        driver_id = request.POST.get('driver')
        amount = request.POST.get('amount')
        
        if driver_id and amount:
            driver = get_object_or_404(TaxiDriver, id=driver_id)
            booking.driver = driver
            booking.amount = amount
            booking.status = 'APPROVED'
            booking.save()
            
            # Create Razorpay order
            order_amount = int(float(amount) * 100)  # Convert to paise
            order_currency = 'INR'
            razorpay_order = razorpay_client.order.create({
                'amount': order_amount,
                'currency': order_currency,
                'payment_capture': '1'
            })
            
            booking.payment_id = razorpay_order['id']
            booking.save()
            
            messages.success(request, "Taxi request approved successfully!")
            return redirect('manage_taxi_bookings')
    
    available_drivers = TaxiDriver.objects.filter(
        organization=booking.organization,
        is_available=True
    )
    
    context = {
        'booking': booking,
        'drivers': available_drivers
    }
    return render(request, 'Organizations/approve_taxi_request.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_taxi_bookings(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    try:
        user = User.objects.get(id=request.session['user_id'])
        bookings = TaxiBooking.objects.filter(patient=user).select_related(
            'organization',
            'driver',
            'driver__user'
        ).order_by('-booking_time')
        
        context = {
            'bookings': bookings,
            'user': user
        }
        return render(request, 'Users/view_taxi_bookings.html', context)
        
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('login')

@require_POST
def taxi_payment_callback(request):
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_signature = request.POST.get('razorpay_signature')
    booking_id = request.POST.get('booking_id')

    try:
        booking = TaxiBooking.objects.get(payment_id=razorpay_order_id)
        
        # Verify payment signature
        params_dict = {
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_order_id': razorpay_order_id,
            'razorpay_signature': razorpay_signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Update booking status
        booking.payment_status = 'COMPLETED'
        booking.status = 'COMPLETED'
        booking.save()
        
        # Send confirmation emails
        send_taxi_booking_confirmation(booking)
        
        messages.success(request, "Payment successful! Your taxi booking is confirmed.")
        return redirect('view_taxi_bookings')
        
    except Exception as e:
        messages.error(request, f"Payment verification failed: {str(e)}")
        return redirect('view_taxi_bookings')

def send_taxi_booking_confirmation(booking):
    # Send email to patient
    patient_subject = "Emergency Taxi Booking Confirmation"
    patient_message = render_to_string('emails/taxi_booking_confirmation_patient.html', {
        'booking': booking
    })
    send_mail(
        patient_subject,
        strip_tags(patient_message),
        settings.DEFAULT_FROM_EMAIL,
        [booking.patient.email],
        html_message=patient_message
    )
    
    # Send email to organization
    org_subject = "New Emergency Taxi Booking"
    org_message = render_to_string('emails/taxi_booking_confirmation_org.html', {
        'booking': booking
    })
    send_mail(
        org_subject,
        strip_tags(org_message),
        settings.DEFAULT_FROM_EMAIL,
        [booking.organization.org_email],
        html_message=org_message
    )
    
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_drivers(request):
    if not request.session.get('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    organization = get_object_or_404(Organizations, id=request.session['org_id'])
    
    if request.method == 'POST':
        form = DriverForm(request.POST, request.FILES)
        if form.is_valid():
            driver = form.save(commit=False)
            driver.organization = organization
            
            # Create Razorpay account for driver
            razorpay_account = create_razorpay_account(driver)
            driver.razorpay_account_id = razorpay_account.id
            
            driver.save()
            messages.success(request, "Driver added successfully!")
            return redirect('manage_drivers')
    else:
        form = DriverForm()
    
    drivers = TaxiDriver.objects.filter(organization=organization)
    context = {
        'form': form,
        'drivers': drivers
    }
    return render(request, 'Organizations/manage_drivers.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_fare_stages(request):
    if not request.session.get('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    organization = get_object_or_404(Organizations, id=request.session['org_id'])
    
    if request.method == 'POST':
        form = FareStageForm(request.POST)
        if form.is_valid():
            fare_stage = form.save(commit=False)
            fare_stage.organization = organization
            fare_stage.save()
            messages.success(request, "Fare stage added successfully!")
            return redirect('manage_fare_stages')
    else:
        form = FareStageForm()
    
    fare_stages = FareStage.objects.filter(organization=organization)
    context = {
        'form': form,
        'fare_stages': fare_stages
    }
    return render(request, 'Organizations/manage_fare_stages.html', context)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def driver_dashboard(request):
    if not request.session.get('driver_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    try:
        driver = TaxiDriver.objects.get(id=request.session['driver_id'])
    except TaxiDriver.DoesNotExist:
        messages.error(request, "Driver profile not found.")
        return redirect('login')
    
    # Get current booking
    current_booking = TaxiBooking.objects.filter(
        driver=driver,
        status__in=['DRIVER_ASSIGNED', 'STARTED']
    ).first()
    
    # Get today's completed bookings
    today = datetime.now().date()
    completed_bookings = TaxiBooking.objects.filter(
        driver=driver,
        status='COMPLETED',
        end_time__date=today
    ).select_related('patient')
    
    # Calculate today's earnings (safely handle if table doesn't exist)
    try:
        todays_earnings = DriverEarning.objects.filter(
            driver=driver,
            created_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or 0
    except Exception:
        todays_earnings = 0
    
    context = {
        'driver': driver,
        'driver_name': f"{driver.first_name} {driver.last_name}",
        'current_booking': current_booking,
        'completed_bookings': completed_bookings,
        'todays_earnings': todays_earnings,
        'is_available': driver.is_available
    }
    return render(request, 'Drivers/dashboard.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def apply_leave(request):
    if not request.session.get('driver_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('driver_login')
    
    driver = get_object_or_404(TaxiDriver, id=request.session['driver_id'])
    
    if request.method == 'POST':
        form = DriverLeaveForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.driver = driver
            leave.status = 'PENDING'
            leave.save()
            
            # Notify organization
            notify_organization_about_leave(leave)
            
            messages.success(request, "Leave application submitted successfully!")
            return redirect('driver_dashboard')
    else:
        form = DriverLeaveForm()
    
    previous_leaves = DriverLeave.objects.filter(driver=driver).order_by('-created_at')
    
    context = {
        'form': form,
        'previous_leaves': previous_leaves
    }
    return render(request, 'Drivers/apply_leave.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def driver_forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        driver = TaxiDriver.objects.filter(email=email).first()
        
        if driver:
            # Generate verification token
            driver.verification_token = get_random_string(64)
            driver.save()
            
            # Send reset password email
            reset_url = request.build_absolute_uri(
                reverse('driver_reset_password', args=[driver.verification_token])
            )
            
            send_mail(
                'Reset Your Password',
                f'Click here to reset your password: {reset_url}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            messages.success(request, "Password reset link sent to your email.")
            return redirect('login')
        else:
            messages.error(request, "No driver account found with this email.")
    
    return render(request, 'Drivers/forgot_password.html')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def driver_reset_password(request, token):
    driver = get_object_or_404(TaxiDriver, verification_token=token)
    
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if password1 != password2:
            messages.error(request, "Passwords don't match!")
            return redirect('driver_reset_password', token=token)
        
        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long!")
            return redirect('driver_reset_password', token=token)
        
        # Update password
        driver.password = make_password(password1)
        driver.verification_token = None  # Clear the token
        driver.save()
        
        messages.success(request, "Password reset successfully! Please login with your new password.")
        return redirect('login')
    
    return render(request, 'Drivers/reset_password.html', {'token': token})

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def submit_complaint(request, booking_id):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    booking = get_object_or_404(TaxiBooking, 
                               id=booking_id, 
                               patient_id=request.session['user_id'])
    
    if request.method == 'POST':
        form = ComplaintForm(request.POST)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.booking = booking
            complaint.save()
            
            # Notify organization and driver
            notify_about_complaint(complaint)
            
            messages.success(request, "Complaint submitted successfully!")
            return redirect('view_taxi_bookings')
    else:
        form = ComplaintForm()
    
    context = {
        'form': form,
        'booking': booking
    }
    return render(request, 'Users/submit_complaint.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_complaints(request):
    if not request.session.get('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    organization = get_object_or_404(Organizations, id=request.session['org_id'])
    
    complaints = TaxiComplaint.objects.filter(
        booking__organization=organization
    ).select_related('booking', 'booking__patient', 'booking__driver')
    
    context = {
        'complaints': complaints
    }
    return render(request, 'Organizations/manage_complaints.html', context)

def process_taxi_payment(request):
    if request.method == 'POST':
        try:
            # Verify Razorpay signature
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_signature = request.POST.get('razorpay_signature')
            booking_id = request.POST.get('booking_id')
            
            booking = get_object_or_404(TaxiBooking, id=booking_id)
            
            # Verify payment signature
            if verify_razorpay_signature(
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature
            ):
                # Update booking status
                booking.payment_status = 'COMPLETED'
                booking.payment_id = razorpay_payment_id
                booking.save()
                
                # Transfer money to driver's account
                transfer_to_driver(booking)
                
                # Send notifications
                notify_payment_success(booking)
                
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid signature'})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def driver_earnings(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    try:
        driver = TaxiDriver.objects.get(user_id=request.session['user_id'])
    except TaxiDriver.DoesNotExist:
        messages.error(request, "Driver profile not found.")
        return redirect('login')
    
    # Get date range from request or default to last 30 days
    end_date = datetime.strptime(request.GET.get('end_date', datetime.now().date().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
    start_date = datetime.strptime(request.GET.get('start_date', (end_date - timedelta(days=30)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
    
    # Get earnings data
    earnings_data = DriverEarning.objects.filter(
        driver=driver,
        booking__end_time__date__range=[start_date, end_date]
    ).annotate(
        date=TruncDate('booking__end_time')
    ).values('date').annotate(
        earnings=Sum('amount'),
        rides=Count('id'),
        total_distance=Sum('booking__distance_km'),
        avg_rating=Avg('booking__patient_rating')
    ).order_by('date')
    
    # Prepare chart data
    dates = []
    earnings = []
    for data in earnings_data:
        dates.append(data['date'].strftime('%b %d'))
        earnings.append(float(data['earnings']))
    
    # Calculate summary
    summary = earnings_data.aggregate(
        total_earnings=Sum('earnings'),
        total_rides=Sum('rides'),
    )
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'daily_earnings': earnings_data,
        'total_earnings': summary['total_earnings'] or 0,
        'total_rides': summary['total_rides'] or 0,
        'average_per_ride': (summary['total_earnings'] / summary['total_rides']) if summary['total_rides'] else 0,
        'dates': json.dumps(dates),
        'earnings': json.dumps(earnings)
    }
    return render(request, 'Drivers/earnings.html', context)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def driver_leave(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    try:
        driver = TaxiDriver.objects.get(user_id=request.session['user_id'])
    except TaxiDriver.DoesNotExist:
        messages.error(request, "Driver profile not found.")
        return redirect('login')
    
    if request.method == 'POST':
        try:
            data = request.POST
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            
            # Validate dates
            if start_date < datetime.now().date():
                return JsonResponse({
                    'success': False,
                    'message': 'Start date cannot be in the past'
                })
            
            if end_date < start_date:
                return JsonResponse({
                    'success': False,
                    'message': 'End date cannot be before start date'
                })
            
            # Check for overlapping leaves
            overlapping_leave = DriverLeave.objects.filter(
                driver=driver,
                status='APPROVED',
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exists()
            
            if overlapping_leave:
                return JsonResponse({
                    'success': False,
                    'message': 'You already have approved leave during this period'
                })
            
            # Create leave request
            leave = DriverLeave.objects.create(
                driver=driver,
                start_date=start_date,
                end_date=end_date,
                leave_type=data['leave_type'],
                reason=data['reason']
            )
            
            # Notify organization
            notify_organization_about_leave(leave)
            
            return JsonResponse({
                'success': True,
                'message': 'Leave request submitted successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    # Get leave history
    leave_history = DriverLeave.objects.filter(driver=driver)
    
    context = {
        'today': datetime.now().date(),
        'leave_history': leave_history
    }
    return render(request, 'Drivers/leave.html', context)


@require_POST
def toggle_driver_availability(request):
    if not request.session.get('user_id'):
        return JsonResponse({
            'success': False,
            'message': 'Please log in to continue'
        })
    
    try:
        data = json.loads(request.body)
        driver = TaxiDriver.objects.get(user_id=request.session['user_id'])
        
        # Check if driver has ongoing ride
        has_ongoing_ride = TaxiBooking.objects.filter(
            driver=driver,
            status__in=['DRIVER_ASSIGNED', 'STARTED']
        ).exists()
        
        if has_ongoing_ride and not data['is_available']:
            return JsonResponse({
                'success': False,
                'message': 'Cannot go offline while having an ongoing ride'
            })
        
        driver.is_available = data['is_available']
        driver.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Status updated successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
        
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_leaves(request):
    if not request.session.get('org_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    organization = get_object_or_404(Organizations, id=request.session['org_id'])
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Get all leave requests for the organization
    pending_requests = DriverLeave.objects.filter(
        driver__organization=organization,
        status='PENDING'
    ).select_related('driver', 'driver__user').order_by('start_date')
    
    approved_leaves = DriverLeave.objects.filter(
        driver__organization=organization,
        status='APPROVED'
    ).select_related('driver', 'driver__user').order_by('-start_date')
    
    rejected_leaves = DriverLeave.objects.filter(
        driver__organization=organization,
        status='REJECTED'
    ).select_related('driver', 'driver__user').order_by('-updated_at')
    
    # Calculate statistics
    stats = {
        'pending_leaves': pending_requests.count(),
        'approved_today': DriverLeave.objects.filter(
            driver__organization=organization,
            status='APPROVED',
            updated_at__date=today
        ).count(),
        'on_leave': DriverLeave.objects.filter(
            driver__organization=organization,
            status='APPROVED',
            start_date__lte=today,
            end_date__gte=today
        ).count(),
        'rejected_month': DriverLeave.objects.filter(
            driver__organization=organization,
            status='REJECTED',
            updated_at__date__gte=month_start
        ).count()
    }
    
    context = {
        'pending_requests': pending_requests,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,
        'today': today,
        **stats
    }
    
    return render(request, 'Organizations/manage_leaves.html', context)

@require_POST
def handle_leave_request(request):
    if not request.session.get('org_id'):
        return JsonResponse({
            'success': False,
            'message': 'Please log in to continue'
        })
    
    try:
        organization = Organizations.objects.get(id=request.session['org_id'])
        leave_id = request.POST.get('leave_id')
        action = request.POST.get('action')
        response_note = request.POST.get('response_note')
        
        leave_request = DriverLeave.objects.get(
            id=leave_id,
            driver__organization=organization,
            status='PENDING'
        )
        
        if action == 'approve':
            # Check for overlapping approved leaves
            overlapping = DriverLeave.objects.filter(
                driver=leave_request.driver,
                status='APPROVED',
                start_date__lte=leave_request.end_date,
                end_date__gte=leave_request.start_date
            ).exists()
            
            if overlapping:
                return JsonResponse({
                    'success': False,
                    'message': 'There is already an approved leave during this period'
                })
            
            leave_request.status = 'APPROVED'
        elif action == 'reject':
            leave_request.status = 'REJECTED'
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid action'
            })
        
        leave_request.response_note = response_note
        leave_request.save()
        
        # Send notification to driver
        notify_driver_about_leave_response(leave_request)
        
        return JsonResponse({
            'success': True,
            'message': f'Leave request {action}d successfully'
        })
        
    except (Organizations.DoesNotExist, DriverLeave.DoesNotExist):
        return JsonResponse({
            'success': False,
            'message': 'Invalid request'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@organization_login_required
def view_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id, organization_id=request.session.get('org_id'))
    context = {
        'service_request': service_request
    }
    return render(request, 'Organizations/view_request.html', context)

@organization_login_required
def approve_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id, organization_id=request.session.get('org_id'))
    try:
        service_request.status = 'approved'
        service_request.save()
        messages.success(request, 'Service request approved successfully.')
    except Exception as e:
        messages.error(request, f'Error approving request: {str(e)}')
    return redirect('pending_requests')

@organization_login_required
def reject_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id, organization_id=request.session.get('org_id'))
    try:
        service_request.status = 'rejected'
        service_request.save()
        messages.success(request, 'Service request rejected successfully.')
    except Exception as e:
        messages.error(request, f'Error rejecting request: {str(e)}')
    return redirect('pending_requests')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def upcoming_team_visits(request):
    if not request.session.get('user_id'):
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    patient = get_object_or_404(User, id=request.session['user_id'])
    
    # Get upcoming team visits for the patient
    team_visits = TeamVisit.objects.filter(
        patient=patient,
        scheduled_date__gte=timezone.now().date()
    ).order_by('scheduled_date', 'start_time')

    context = {
        'team_visits': team_visits,
        'patient': patient,
    }
    
    return render(request, 'Users/upcoming_team_visits.html', context)


from django.views.decorators.csrf import csrf_protect

@team_login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def team_dashboard(request):
    try:
        current_time = timezone.now()
        
        # Get patients with scheduled visits
        scheduled_patients = User.objects.filter(
            team_visits__team=request.team_membership.team,
            team_visits__status='SCHEDULED',
            team_visits__scheduled_date__gte=current_time,
            is_active=True
        ).distinct().order_by('first_name')
        
        scheduled_visits = TeamVisit.objects.filter(
            team=request.team_membership.team,
            status='SCHEDULED',
            scheduled_date__gte=current_time
        ).select_related('patient').order_by('scheduled_date')[:5]

        completed_visits = TeamVisit.objects.filter(
            team=request.team_membership.team,
            status='COMPLETED'
        ).select_related('patient').order_by('-scheduled_date')[:10]

        context = {
            'staff': request.team_membership.staff,
            'team': request.team_membership.team,
            'role': request.team_membership.role,
            'patients': scheduled_patients,
            'scheduled_visits': scheduled_visits,
            'completed_visits': completed_visits,
        }

        return render(request, 'teams/dashboard.html', context)

    except TeamVisit.DoesNotExist:
        messages.warning(request, "No scheduled visits found for your team.")
        return render(request, 'teams/dashboard.html', {
            'staff': request.team_membership.staff,
            'team': request.team_membership.team,
            'role': request.team_membership.role
        })
    
    except User.DoesNotExist:
        messages.error(request, "Error accessing patient records. Please try again later.")
        return redirect('login')
    
    except OperationalError:
        messages.error(request, "Database connection error. Please try again later.")
        return redirect('login')
    
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        # Log the error here if you have logging configured
        return redirect('login')
    
    
@team_login_required
def get_patient_details(request, patient_id):
    try:
        # Get the patient and their latest visit
        patient = get_object_or_404(User, id=patient_id)
        latest_visit = PatientVisitRecord.objects.filter(
            patient=patient,
            team=request.team_membership.team
        ).order_by('-visit_date').first()

        if latest_visit:
            previous_vitals = {
                'blood_pressure': latest_visit.blood_pressure,
                'pulse_rate': latest_visit.pulse_rate,
                'temperature': latest_visit.temperature,
                'respiratory_rate': latest_visit.respiratory_rate,
                'oxygen_saturation': latest_visit.oxygen_saturation
            }

            return JsonResponse({
                'status': 'success',
                'previous_vitals': previous_vitals,
                'medical_history': latest_visit.medical_conditions
            })
        
        return JsonResponse({
            'status': 'success',
            'previous_vitals': None,
            'medical_history': None
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@team_login_required
@require_http_methods(["POST"])
def save_patient_data(request):
    try:
        patient_id = request.POST.get('patient_id')
        if not patient_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Patient ID is required'
            }, status=400)

        team = request.team_membership.team
        current_time = timezone.now()

        # Create visit record
        visit_record = PatientVisitRecord.objects.create(
            patient_id=int(patient_id),
            team=team,
            staff=request.team_membership.staff,
            visit_date=current_time,
            blood_pressure=request.POST.get('blood_pressure'),
            pulse_rate=request.POST.get('pulse_rate'),
            temperature=request.POST.get('temperature'),
            respiratory_rate=request.POST.get('respiratory_rate'),
            oxygen_saturation=request.POST.get('oxygen_saturation'),
            pain_score=request.POST.get('pain_score'),
            pain_location=request.POST.get('pain_location'),
            pain_character=request.POST.get('pain_character'),
            medical_conditions=request.POST.get('medical_conditions'),
            symptoms=request.POST.get('symptoms'),
            medications=request.POST.get('medications'),
            clinical_notes=request.POST.get('clinical_notes'),
            activity_level=request.POST.get('activity_level'),
            weight=request.POST.get('weight'),
            consciousness_level=request.POST.get('consciousness_level'),
            mood_status=request.POST.get('mood_status')
        )

        # Update team visit status
        team_visit = TeamVisit.objects.get(
            patient_id=patient_id,
            team=team,
            status='SCHEDULED'
        )
        team_visit.status = 'COMPLETED'
        team_visit.save()

        # Skip ML predictions for now
        visit_record.visit_priority_score = 0  # Default value
        visit_record.next_visit_recommendation = 7  # Default 7 days
        visit_record.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Visit record saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving patient data: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Visit record saved successfully, but ML predictions could not be generated.',
            'details': str(e)
        }, status=200)  # Still return 200 as the core data was saved

def get_risk_trends(patient_id):
    """Get historical risk trends for a patient"""
    try:
        records = PatientVisitRecord.objects.filter(
            patient_id=patient_id
        ).order_by('-visit_date')[:10]  # Last 10 visits

        return {
            'dates': [record.visit_date.strftime('%Y-%m-%d') for record in records],
            'priority_scores': [float(record.visit_priority_score) for record in records]
        }
    except Exception as e:
        logger.error(f"Error fetching risk trends: {str(e)}")
        return {
            'dates': [],
            'priority_scores': []
        }


@team_login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def visit_report(request, visit_id):
    try:
        visit = TeamVisit.objects.select_related(
            'patient', 'team'
        ).get(
            id=visit_id,
            team=request.team_membership.team,
            status='COMPLETED'
        )
        
        # Get the visit record without date matching
        visit_record = PatientVisitRecord.objects.filter(
            patient=visit.patient,
            team=visit.team
        ).order_by('-created_at').first()  # Get the most recent record
        
        if not visit_record:
            messages.error(request, "Visit record not found.")
            return redirect('team_dashboard')
        
        context = {
            'visit': visit,
            'visit_record': visit_record,
            'staff': request.team_membership.staff,
            'team': request.team_membership.team,
            'report_date': timezone.now(),
        }
        
        return render(request, 'teams/visit_report.html', context)
        
    except TeamVisit.DoesNotExist:
        messages.error(request, "Visit report not found or unauthorized access.")
        return redirect('team_dashboard')

# Add these new view functions
@organization_login_required
@organization_login_required
def patient_risk_history(request):
    # Get patient's visit records
    records = PatientVisitRecord.objects.filter(
        patient_id=request.GET.get('patient_id')
    ).order_by('-visit_date')

    # Calculate risk trends
    risk_data = []
    for record in records:
        calculator = VisitPriorityCalculator()
        priority = calculator.calculate_priority(record)
        risk_data.append({
            'date': record.visit_date,
            'priority_score': priority,
            'vital_signs': {
                'blood_pressure': record.blood_pressure,
                'pulse_rate': record.pulse_rate,
                # ... other vitals ...
            }
        })

    return render(request, 'Organizations/ML/patient_risk_history.html', {
        'risk_data': risk_data
    })

@organization_login_required
def priority_alerts(request):
    # Get high-priority patients
    high_risk_records = PatientVisitRecord.objects.filter(
        visit_priority_score__gte=8.0
    ).select_related('patient').order_by('-visit_priority_score')

    alerts = []
    for record in high_risk_records:
        alerts.append({
            'patient_name': record.patient.get_full_name(),
            'priority_score': record.visit_priority_score,
            'next_visit': record.next_visit_recommendation,
            'risk_factors': {
                'vitals': record.blood_pressure,
                'pain': record.pain_score,
                # ... other factors ...
            }
        })

    return render(request, 'Organizations/ML/priority_alerts.html', {
        'alerts': alerts
    })

@organization_login_required
def risk_comparison(request):
    return render(request, 'Organizations/ML/risk_comparison.html')

@organization_login_required
def risk_monitoring(request):
    return render(request, 'Organizations/ML/risk_monitoring.html')

@organization_login_required
def schedule_optimizer(request):
    return render(request, 'Organizations/ML/schedule_optimizer.html')

@organization_login_required
def team_availability(request):
    return render(request, 'Organizations/ML/team_availability.html')

@organization_login_required
def visit_priority(request):
    return render(request, 'Organizations/ML/visit_priority.html')

# #API Endpoints

# from rest_framework import viewsets
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from ..ml.risk_predictor import RiskPredictor
# from ..ml.priority_calculator import VisitPriorityCalculator

# class HealthPredictionViewSet(viewsets.ViewSet):
#     @action(detail=True, methods=['POST'])
#     def predict_risks(self, request, pk=None):
#         """
#         Endpoint for risk prediction
#         """
#         visit_record = self.get_object()
#         predictor = RiskPredictor()
#         risks = predictor.predict_risks(visit_record)
#         return Response(risks)

#     @action(detail=True, methods=['POST'])
#     def calculate_priority(self, request, pk=None):
#         """
#         Endpoint for priority calculation
#         """
#         visit_record = self.get_object()
#         calculator = VisitPriorityCalculator()
#         priority = calculator.calculate_priority(visit_record)
#         next_visit = calculator.get_next_visit_recommendation(priority)
#         return Response({
#             'priority_score': priority,
#             'next_visit_days': next_visit
#         })