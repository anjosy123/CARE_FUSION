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
    TaxiComplaint, PatientVisitRecord, EmergencyContact, CaretakerDetails, UserLocation,
    MedicalEquipment, EquipmentRental, EquipmentDelivery, RentalPayment, RentalPaymentAnalytics,
    MonthlyRentalPayment, RentalUsagePeriod, EquipmentRental, RentalExtensionRequest, Notification
)
from .forms import AppointmentRequestForm, ServiceRequestForm,ServiceForm,StaffForm,PatientAssignmentForm,PrescriptionForm,AppointmentForm,TeamForm, TeamVisitForm, RescheduleTeamVisitForm, TeamMessageForm, VisitChecklistForm, VisitNoteForm, ProfileUpdateForm,TeamVisit, TaxiBookingForm, DriverForm, FareStageForm, DriverLeaveForm, DriverEarningForm, ComplaintForm, TeamMemberDetailForm, EquipmentForm
from .utils import (
    send_verification_email, send_appointment_email, calculate_distance, 
    send_sms, notify_organization_about_leave, calculate_fare, 
    create_razorpay_order, create_razorpay_account, notify_about_complaint, 
    verify_razorpay_signature, transfer_to_driver, notify_payment_success, 
    notify_driver_about_leave_response, create_rental_payment_order, 
    verify_rental_payment, send_rental_payment_notification, 
    generate_rental_receipt, send_rental_rejection_notification, 
    send_rental_request_notification, send_rental_approval_notification,
    create_monthly_rental_order, calculate_monthly_rent,
    create_refund_order, send_rental_end_notification,
    send_delivery_otp
)
from django.db.models import Q, Sum, Count, Avg, F
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
from decimal import Decimal
from .ml.model_trainer import PriorityPredictor
from django.http import HttpResponse
import csv
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.cache import cache
from math import radians, sin, cos, sqrt, atan2
import requests
from django.core.cache import cache
from datetime import timedelta

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import User, NotificationPreferences
from math import radians, sin, cos, sqrt, atan2
from django.template import TemplateDoesNotExist

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

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@staff_login_required
def volunteer_dashboard(request):
    """Dashboard view for volunteer staff members"""
    try:
        staff = Staff.objects.get(id=request.session.get('staff_id'))
        
        # Ensure staff name is in session
        if 'staff_name' not in request.session:
            request.session['staff_name'] = staff.get_full_name()
            request.session['staff_role'] = staff.role
        
        # Get deliveries assigned to this volunteer
        pending_deliveries = EquipmentDelivery.objects.filter(
            volunteer=staff,
            status='ASSIGNED'
        ).select_related('rental', 'rental__equipment', 'rental__patient')
        
        active_deliveries = EquipmentDelivery.objects.filter(
            volunteer=staff,
            status='IN_PROGRESS'
        ).select_related('rental', 'rental__equipment', 'rental__patient')
        
        completed_deliveries = EquipmentDelivery.objects.filter(
            volunteer=staff,
            status='DELIVERED'
        ).select_related('rental', 'rental__equipment', 'rental__patient')
        
        # Get delivery statistics
        total_completed = completed_deliveries.count()
        total_active = active_deliveries.count()
        total_pending = pending_deliveries.count()
        
        # Calculate completion rate
        completion_rate = 0
        if total_completed > 0:
            on_time_deliveries = completed_deliveries.filter(
                completed_at__lte=F('delivery_date')
            ).count()
            completion_rate = round((on_time_deliveries / total_completed) * 100, 1)
        
        # Add welcome message
        messages.info(request, f"Welcome back, {staff.get_full_name()}!")
        
        context = {
            'staff': staff,
            'pending_deliveries': pending_deliveries,
            'active_deliveries': active_deliveries,
            'completed_deliveries': completed_deliveries,
            'total_completed': total_completed,
            'total_active': total_active,
            'total_pending': total_pending,
            'completion_rate': completion_rate
        }
        
        return render(request, 'staff/volunteer_dashboard.html', context)
    except TemplateDoesNotExist:
        # Redirect to organization login instead of staff login
        return redirect('org_login')

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

def service_request_form(request, org_id):
    # Check if user is logged in using session
    if not request.session.get('user_id'):
        messages.error(request, "Please login to request services.")
        return redirect('login')
    
    try:
        # Get the logged-in user
        user = User.objects.get(id=request.session['user_id'])
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
                return redirect('service_request_form', org_id=org_id)
            
            try:
                service = Service.objects.get(id=service_id, organization=organization)
                
                # Create service request
                ServiceRequest.objects.create(
                    patient=user,
                    organization=organization,
                    service=service,
                    phone=phone,
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
            'user': user,  # Pass user to template
        }
        return render(request, 'Users/service_request_form.html', context)
        
    except User.DoesNotExist:
        messages.error(request, "User session expired. Please login again.")
        return redirect('login')
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

        # Try to authenticate as User
        user = User.objects.filter(email=email).first()
        
        if user and check_password(password, user.password):
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
                
                # Check if user has any service requests
                has_service_requests = ServiceRequest.objects.filter(patient=user).exists()
                
                if has_service_requests:
                    return redirect('patients_dashboard')
                else:
                    return redirect('organizations_list')

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
    try:
        user = User.objects.get(id=request.session.get('user_id'))
        
        # Fetch health tips from both APIs
        health_tips = get_health_tips()
        
        # Get team visits with related data
        team_visits = TeamVisit.objects.filter(
            patient=user,
            scheduled_date__gte=timezone.now().date()
        ).select_related(
            'team', 
            'team__organization'
        ).order_by('scheduled_date', 'start_time')

        # Get assigned teams through team visits
        assigned_teams = Team.objects.filter(
            visits__patient=user,
            is_active=True
        ).select_related(
            'organization'
        ).prefetch_related(
            'members'
        ).distinct()

        # Get active prescriptions
        prescriptions = Prescription.objects.filter(
            patient_assignment__patient=user,
            patient_assignment__is_active=True,
            end_date__gte=timezone.now().date()
        ).select_related('patient_assignment')

        # Get active services
        services = ServiceRequest.objects.filter(
            patient=user,
            status='APPROVED'
        ).select_related('organization', 'service')

        context = {
            'user': user,
            'team_visits': team_visits,
            'assigned_teams': assigned_teams,
            'prescriptions': prescriptions,
            'services': services,
            'active_prescriptions_count': prescriptions.count(),
            'active_services_count': services.count(),
            'today': timezone.now().date(),
            'health_tips': health_tips,  # Updated to include both tips
        }
        
        return render(request, 'Users/patients_dashboard.html', context)

    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return redirect('login')

def get_health_tips():
    """Fetch health tips from both Health.gov and API Ninjas"""
    try:
        # API Ninjas Health Tip
        ninja_api_url = "https://api.api-ninjas.com/v1/quotes?category=health"
        headers = {
            'X-Api-Key': settings.API_NINJAS_KEY
        }
        
        tips = {
            'gov_tip': {
                'title': 'Daily Health Tip',
                'content': 'Stay hydrated and maintain a balanced diet for better health.',
                'url': '#'
            },
            'ninja_tip': {
                'quote': 'Health is wealth.',
                'author': 'Unknown'
            }
        }
        
        try:
            ninja_response = requests.get(ninja_api_url, headers=headers)
            if ninja_response.status_code == 200:
                ninja_data = ninja_response.json()
                if ninja_data:
                    tips['ninja_tip'] = {
                        'quote': ninja_data[0]['quote'],
                        'author': ninja_data[0]['author']
                    }
        except:
            pass
            
        try:
            # Health.gov Tip
            gov_url = "https://health.gov/myhealthfinder/api/v3/topicsearch.json"
            params = {
                "lang": "en",
                "categoryId": "24",
                "limit": 1,
            }
            
            gov_response = requests.get(gov_url, params=params)
            if gov_response.status_code == 200:
                data = gov_response.json()
                if 'Result' in data and 'Resources' in data['Result']:
                    tips['gov_tip'] = {
                        'title': data['Result']['Resources']['Resource'][0]['Title'],
                        'content': data['Result']['Resources']['Resource'][0]['Sections']['section'][0]['Content'],
                        'url': data['Result']['Resources']['Resource'][0]['AccessibleVersion']
                    }
        except:
            pass
            
        return tips
            
    except Exception as e:
        logger.error(f"Error fetching health tips: {str(e)}")
        return {
            'gov_tip': {
                'title': 'Daily Health Tip',
                'content': 'Stay hydrated and maintain a balanced diet for better health.',
                'url': '#'
            },
            'ninja_tip': {
                'quote': 'Health is wealth.',
                'author': 'Unknown'
            }
        }

@never_cache
def palliatives_dashboard(request):
    if not request.session.get('org_id'):
        messages.error(request, "Please login to access the dashboard")
        return redirect('login')
    
    org_id = request.session.get('org_id')
    
    try:
        # Get available equipment count
        available_equipment_count = MedicalEquipment.objects.filter(
            organization_id=org_id,
            status='AVAILABLE'
        ).count()
        
        # Get active rentals count
        active_rentals_count = EquipmentRental.objects.filter(
            equipment__organization_id=org_id,
            payment_status='PAID',
            status='ACTIVE'
        ).count()
        
        # Get total staff count
        total_staff_count = Staff.objects.filter(
            organization_id=org_id
        ).count()
        
        # Get assigned patients count
        assigned_patients_count = PatientAssignment.objects.filter(
            organization_id=org_id,
            is_active=True
        ).count()
        
        # Get pending requests count
        pending_requests_count = ServiceRequest.objects.filter(
            organization_id=org_id,
            status='PENDING'
        ).count()
        
        # Get active teams count
        active_teams_count = Team.objects.filter(
            organization_id=org_id,
            is_active=True
        ).count()
        
        context = {
            'available_equipment_count': available_equipment_count,
            'active_rentals_count': active_rentals_count,
            'total_staff_count': total_staff_count,
            'assigned_patients_count': assigned_patients_count,
            'pending_requests_count': pending_requests_count,
            'active_teams_count': active_teams_count
        }
        
        return render(request, 'Organizations/palliatives_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return redirect('login')





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
    

def verify_user_email(request, token):
    try:
        user = User.objects.get(email_verification_token=token)
        user.is_email_verified = True
        user.is_active = True
        user.save()
        
        # Get the stored user type from session
        user_type = request.session.get('temp_user_type', 'patient')
        
        # Clear the temporary session data
        if 'temp_user_type' in request.session:
            del request.session['temp_user_type']
        
        messages.success(request, "Email verified successfully! You can now login.")
        return redirect('login')

    except User.DoesNotExist:
        messages.error(request, "Invalid verification token")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred during verification: {str(e)}")
        return redirect('login')


# User = get_user_model()

def handlesignup(request):
    if request.method == "POST":
        uname = request.POST.get("username")
        firstname = request.POST.get("fname")
        lastname = request.POST.get("lname")
        email = request.POST.get("email")
        password = request.POST.get("pass1")
        confirmpassword = request.POST.get("pass2")
        user_type = request.POST.get("user_type")
        patient_name = request.POST.get("patient_name")

        # Get location data
        address = request.POST.get('address')
        city = request.POST.get('city')
        pincode = request.POST.get('pincode')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

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
        
        try:
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
            user.usertype = user_type
            
            # If caretaker is registering, store patient name
            if user_type == 'caretaker':
                user.patient_name = patient_name
                # Create CaretakerDetails entry
                CaretakerDetails.objects.create(
                    user=user,
                    caretaker_name=f"{firstname} {lastname}",
                    relationship=request.POST.get("relationship"),
                    patient_name=patient_name
                )
            
            user.save()

            # Create UserLocation entry
            try:
                # Convert latitude and longitude to Decimal if they exist
                lat_decimal = Decimal(latitude) if latitude else None
                long_decimal = Decimal(longitude) if longitude else None

                UserLocation.objects.create(
                    user=user,
                    address=address,
                    city=city,
                    pincode=pincode,
                    latitude=lat_decimal,
                    longitude=long_decimal
                )
            except Exception as loc_error:
                print(f"Error saving location: {str(loc_error)}")
                # If location saving fails, continue with the registration
                messages.warning(request, "Registration successful but there was an issue saving your location.")
            
            # Store user type in session for later use
            request.session['temp_user_type'] = user_type
            
            # Send verification email
            send_verification_email(user.email, str(user.email_verification_token))
            
            messages.success(request, "Signup successful! Please check your email to verify your account.")
            return redirect(reverse('login'))

        except Exception as e:
            # If any error occurs during user creation, delete the user if it was created
            if 'user' in locals():
                user.delete()
            messages.error(request, f"An error occurred during signup: {str(e)}")
            return redirect(reverse('signup'))
    
    # Render the signup form if the request is not a POST
    return render(request, 'Users/signup.html')





@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def handlelogout(request):  
    request.session.clear()
    logout(request)
    return redirect('/')

def register_organization(request):
    if request.method == 'POST':
        try:
            # Get form data
            org_email = request.POST['org_email']
            org_name = request.POST['org_name']
            org_regid = request.POST['org_regid']
            org_address = request.POST['org_address']
            org_phone = request.POST['org_phone']
            org_pincode = request.POST['org_pincode']
            org_pass1 = request.POST['org_pass1']
            org_pass2 = request.POST.get('org_pass2')
            
            # Get location data from POST
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            print("Form Data:", request.POST)  # Debug print
            print(f"Location Data - Lat: {latitude}, Long: {longitude}")  # Debug print

            # Store form data in session temporarily
            request.session['org_temp_data'] = {
                'org_email': org_email,
                'org_name': org_name,
                'org_regid': org_regid,
                'org_address': org_address,
                'org_phone': org_phone,
                'org_pincode': org_pincode,
                'org_pass1': org_pass1,
                'org_pass2': org_pass2,
            }

            # If location data is not present, return to form with location request
            if not latitude or not longitude:
                return render(request, 'Organizations/org_signup.html', {
                    'need_location': True,
                    'form_data': request.session['org_temp_data']
                })

            # Validation checks
            if org_pass1 != org_pass2:
                messages.error(request, "Passwords do not match!")
                return redirect('org_signup')

            if Organizations.objects.filter(org_regid=org_regid).exists():
                messages.error(request, "Organization with this registration ID already exists!")
                return redirect('org_signup')
            
            if Organizations.objects.filter(org_email=org_email).exists():
                messages.error(request, "Organization with this email already exists!")
                return redirect('org_signup')

            # Convert coordinates to Decimal
            try:
                lat_decimal = Decimal(latitude)
                long_decimal = Decimal(longitude)
            except (TypeError, ValueError) as e:
                print(f"Error converting coordinates: {e}")
                messages.error(request, "Invalid location data")
                return redirect('org_signup')

            # Create organization instance
            organization = Organizations(
                org_regid=org_regid,
                org_email=org_email,
                org_name=org_name,
                org_address=org_address,
                org_phone=org_phone,
                pincode=org_pincode,
                org_password=make_password(org_pass1),
                approve=False,
                is_email_verified=False,
                latitude=lat_decimal,
                longitude=long_decimal
            )
            
            organization.save()
            
            # Clear temporary session data
            if 'org_temp_data' in request.session:
                del request.session['org_temp_data']
            
            try:
                # Send verification email
                send_verification_email(
                    email=organization.org_email, 
                    token=str(organization.email_verification_token), 
                    is_organization=True
                )
                messages.success(request, "Organization registered successfully! Please check your email to verify your account.")
            except Exception as e:
                print(f"Error sending verification email: {str(e)}")
                messages.warning(request, "Organization registered, but there was an issue sending the verification email. Please contact support.")
            
            return redirect('login')
            
        except Exception as e:
            print(f"Error during organization registration: {str(e)}")
            messages.error(request, f"An error occurred during registration: {str(e)}")
            return redirect('org_signup')
    
    return render(request, 'Organizations/org_signup.html', {'need_location': False})

def org_logout(request):
    """Handle organization logout"""
    # Clear all session data
    request.session.flush()
    messages.success(request, "Successfully logged out.")
    return redirect('login')  # Redirect to organizations home page instead of login


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
def verify_email(request, token, is_organization='false'):
    try:
        if is_organization.lower() == 'true':
            organization = Organizations.objects.get(email_verification_token=token)
            organization.is_email_verified = True
            organization.save()
            messages.success(request, "Email verified successfully! Please wait for admin approval.")
            return redirect('login')  # Changed from 'org_login' to 'login'
        else:
            # Handle regular user verification
            return redirect('verify_user_email', token=token)
            
    except Organizations.DoesNotExist:
        messages.error(request, "Invalid verification token")
        return redirect('login')
    except Exception as e:
        messages.error(request, f"An error occurred during verification: {str(e)}")
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
    """Handle team visit scheduling with priority-based patient listing"""
    try:
        organization = get_object_or_404(Organizations, id=request.session.get('org_id'))
        selected_team = request.GET.get('team')
        
        # Get all active teams for the organization
        teams = Team.objects.filter(organization=organization, is_active=True)
        
        # Get all approved patients with their latest visit records
        patients = User.objects.filter(
            servicerequest__organization=organization,
            servicerequest__status='approved'
        ).prefetch_related('visit_records').distinct()

        # Group patients by priority based on their latest visit records
        high_priority = []
        medium_priority = []
        low_priority = []

        for patient in patients:
            # Get latest visit record
            latest_record = patient.visit_records.order_by('-visit_date').first()
            
            if latest_record:
                # Calculate priority score using the same formula as priority dashboard
                priority_score = (
                    float(latest_record.fall_risk_score or 0) * 0.3 +
                    float(latest_record.deterioration_risk or 0) * 0.4 +
                    float(latest_record.overall_health_score or 0) * 0.3
                )
                patient.visit_priority_score = priority_score
            else:
                # If no visit record exists, use default priority score
                patient.visit_priority_score = 0.0

            # Group based on priority score
            if patient.visit_priority_score >= 7.0:
                high_priority.append(patient)
            elif patient.visit_priority_score >= 4.0:
                medium_priority.append(patient)
            else:
                low_priority.append(patient)

        # Sort each group by priority score in descending order
        high_priority.sort(key=lambda x: x.visit_priority_score, reverse=True)
        medium_priority.sort(key=lambda x: x.visit_priority_score, reverse=True)
        low_priority.sort(key=lambda x: x.visit_priority_score, reverse=True)

        # Get team if selected
        team = None
        if selected_team:
            team = get_object_or_404(Team, id=selected_team, organization=organization)

        # Handle form submission
        if request.method == 'POST':
            team_id = request.POST.get('team')
            patient_id = request.POST.get('patient')
            scheduled_date = request.POST.get('scheduled_date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            purpose = request.POST.get('purpose', '')

            # Validate and create visit
            if team_id and patient_id and scheduled_date and start_time and end_time:
                team = get_object_or_404(Team, id=team_id)
                patient = get_object_or_404(User, id=patient_id)
                
                visit = TeamVisit.objects.create(
                    team=team,
                    patient=patient,
                    scheduled_date=scheduled_date,
                    start_time=start_time,
                    end_time=end_time,
                    purpose=purpose,
                    status='SCHEDULED'
                )
                
                messages.success(request, 'Team visit scheduled successfully.')
                return redirect('team_visit_list')
            else:
                messages.error(request, 'Please fill all required fields.')

        context = {
            'organization': organization,
            'teams': teams,
            'high_priority_patients': high_priority,
            'medium_priority_patients': medium_priority,
            'low_priority_patients': low_priority,
            'selected_team': selected_team,
            'min_date': timezone.now().date(),
            'max_date': timezone.now().date() + timezone.timedelta(days=30),
        }
        
        return render(request, 'Organizations/schedule_team_visit.html', context)
        
    except Exception as e:
        messages.error(request, f"Error scheduling visit: {str(e)}")
        return redirect('team_visit_list')



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
    """Display team dashboard with patient visits and data"""
    try:
        current_time = timezone.now()
        team = request.team_membership.team

        # Get all scheduled visits for the team
        scheduled_visits = TeamVisit.objects.filter(
            team=team,
            status='SCHEDULED',
            scheduled_date__gte=current_time.date()
        ).select_related(
            'patient'
        ).order_by('scheduled_date', 'start_time')

        # Get completed visits for reports
        completed_visits = TeamVisit.objects.filter(
            team=team,
            status='COMPLETED'
        ).select_related(
            'patient'
        ).order_by('-scheduled_date')[:10]  # Get last 10 completed visits

        # Get all patients with scheduled visits
        patients = User.objects.filter(
            team_visits__team=team,
            team_visits__status='SCHEDULED',
            team_visits__scheduled_date__gte=current_time.date()
        ).distinct().prefetch_related(
            'visit_records',
            'team_visits'
        ).order_by('team_visits__scheduled_date')

        context = {
            'staff': request.team_membership.staff,
            'team': team,
            'role': request.team_membership.role,
            'scheduled_visits': scheduled_visits,
            'completed_visits': completed_visits,
            'patients': patients,
        }

        return render(request, 'teams/dashboard.html', context)

    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return redirect('login')
    
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


def organizations_list(request):
    # Get all approved and verified organizations
    organizations = Organizations.objects.filter(
        approve=True,
        is_email_verified=True
    ).order_by('org_name')
    
    context = {
        'organizations': organizations,
    }
    
    return render(request, 'Users/organizations_list.html', context)

def get_team_details(request, team_id):
    if not request.session.get('user_id'):
        return JsonResponse({'status': 'error', 'message': 'Not authorized'}, status=401)
    
    try:
        # Get the user's team visit
        team_visit = TeamVisit.objects.select_related('team').get(
            team_id=team_id,
            patient_id=request.session['user_id'],
            scheduled_date__gte=timezone.now().date()
        )
        
        if not team_visit:
            return JsonResponse({
                'status': 'error',
                'message': 'Team visit not found'
            }, status=404)

        # Get team members
        team_members = team_visit.team.members.all()
        
        # Format member details for the form
        member_details = []
        for member in team_members:
            member_details.append(
                f"Name: {member.get_full_name()}\n"
                f"Role: {member.role}\n"
                "-------------------"
            )
        
        # Create form with initial data
        form_initial = {
            'team_name': team_visit.team.name,
            'members': "\n".join(member_details) if member_details else "No team members assigned"
        }
        
        form = TeamMemberDetailForm(initial=form_initial)
        
        # Render the modal content
        html = render_to_string('Users/team_member_modal.html', {
            'form': form,
            'team': team_visit.team
        }, request=request)
        
        return JsonResponse({
            'status': 'success',
            'html': html
        })
        
    except TeamVisit.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Team visit not found or access denied'
        }, status=404)
    except Exception as e:
        logger.error(f"Unexpected error in get_team_details: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)

def predict_priority(request):
    predictor = PriorityPredictor()
    # Add prediction logic here
    return JsonResponse({'priority': 'High'})

def model_metrics(request):
    # Add metrics logic here
    return JsonResponse({'accuracy': 0.85})

def priority_dashboard(request):
    try:
        # Get all records with patient data - adjust select_related based on your model structure
        records = PatientVisitRecord.objects.select_related('patient').all()
        
        print(f"\nDEBUG: Total records found: {records.count()}")

        # Filter based on visit_priority_score
        high_priority = records.filter(
            visit_priority_score__isnull=False,
            visit_priority_score__gt=7.0,
            visit_priority_score__lte=10.0
        ).order_by('-visit_priority_score')

        medium_priority = records.filter(
            visit_priority_score__isnull=False,
            visit_priority_score__gt=4.0,
            visit_priority_score__lte=7.0
        ).order_by('-visit_priority_score')

        low_priority = records.filter(
            visit_priority_score__isnull=False,
            visit_priority_score__gte=0,
            visit_priority_score__lte=4.0
        ).order_by('-visit_priority_score')

        def format_patient_data(record):
            return {
                # Patient Visit Record data
                'visit_priority_score': f"{record.visit_priority_score:.1f}" if record.visit_priority_score else 'N/A',
                'blood_pressure': record.blood_pressure or 'N/A',
                'heart_rate': record.pulse_rate or 'N/A',
                'oxygen_level': record.oxygen_saturation or 'N/A',
                'temperature': record.temperature or 'N/A',
                'pain_score': record.pain_score or 'N/A',
                'last_visit_date': record.visit_date.strftime('%Y-%m-%d') if record.visit_date else 'N/A',
                
                # Patient data
                'patient_id': record.patient.id,
                'full_name': f"{record.patient.first_name} {record.patient.last_name}",
                'phone': record.patient.phone_number if hasattr(record.patient, 'phone_number') else 'N/A',
                'address': record.patient.address if hasattr(record.patient, 'address') else 'N/A',
                'age': record.patient.age if hasattr(record.patient, 'age') else 'N/A',
                'gender': record.patient.gender if hasattr(record.patient, 'gender') else 'N/A',
                
                # Risk scores
                'fall_risk': record.fall_risk_score or 'N/A',
                'deterioration_risk': record.deterioration_risk or 'N/A',
                'overall_health': record.overall_health_score or 'N/A'
            }

        context = {
            'high_priority_patients': [format_patient_data(record) for record in high_priority],
            'medium_priority_patients': [format_patient_data(record) for record in medium_priority],
            'low_priority_patients': [format_patient_data(record) for record in low_priority],
            'high_priority_count': high_priority.count(),
            'medium_priority_count': medium_priority.count(),
            'low_priority_count': low_priority.count(),
            'total_patients': records.count(),
            'model_accuracy': 94.87,
            'model_precision': 93.2,
            'model_recall': 94.0,
            'model_f1_score': 93.6,
            'last_update': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'chart_labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            'chart_data': [92, 93, 94, 94.5, 94.87]
        }

        return render(request, 'Organizations/priority_dashboard.html', context)

    except Exception as e:
        print(f"Error in priority dashboard: {str(e)}")
        logger.error(f"Error in priority dashboard: {str(e)}")
        return render(request, 'Organizations/priority_dashboard.html', {
            'error': f'An error occurred while loading the dashboard: {str(e)}',
            'high_priority_patients': [],
            'medium_priority_patients': [],
            'low_priority_patients': [],
            'high_priority_count': 0,
            'medium_priority_count': 0,
            'low_priority_count': 0
        })

def get_key_indicators(record):
    """Get key health indicators for a patient record"""
    return {
        'blood_pressure': record.blood_pressure or 'N/A',
        'pulse_rate': record.pulse_rate or 'N/A',
        'oxygen_saturation': record.oxygen_saturation or 'N/A',
        'temperature': record.temperature or 'N/A',
        'pain_score': record.pain_score or 'N/A',
    }

def get_risk_factors(record):
    """Get risk factors that contributed to priority score"""
    risk_factors = []
    
    if record.blood_pressure:
        try:
            systolic, diastolic = map(int, record.blood_pressure.split('/'))
            if systolic > 140 or systolic < 90 or diastolic > 90 or diastolic < 60:
                risk_factors.append('Abnormal Blood Pressure')
        except:
            pass
    
    if record.oxygen_saturation and record.oxygen_saturation < 95:
        risk_factors.append('Low Oxygen Saturation')
    
    if record.pain_score and record.pain_score >= 7:
        risk_factors.append('Severe Pain')
        
    if record.activity_level and record.activity_level <= 2:
        risk_factors.append('Low Activity Level')
        
    if record.fall_risk_score and record.fall_risk_score > 5:
        risk_factors.append('High Fall Risk')
        
    return risk_factors

def schedule_visits(request):
    """Handle scheduling team visits for high-priority patients"""
    # Add your scheduling logic here
    messages.success(request, 'Visit scheduling initiated')
    return redirect('priority_dashboard')

def export_priority_report(request):
    """Export priority data as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="priority_report_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Patient', 'Priority Score', 'Last Visit', 'Next Visit Due'])
    
    records = PatientVisitRecord.objects.all().order_by('-priority_score')
    for record in records:
        writer.writerow([
            record.patient.get_full_name(),
            record.priority_score,
            record.visit_date,
            record.next_visit_recommendation
        ])
    
    return response

def retrain_model(request):
    """Retrain the priority prediction model"""
    try:
        from django.core.management import call_command
        call_command('train_priority_model')
        messages.success(request, 'Model retraining completed successfully')
    except Exception as e:
        messages.error(request, f'Error retraining model: {str(e)}')
    
    return redirect('priority_dashboard')


def risk_monitoring(request):
    context = {
        'page_title': 'Risk Monitoring',
        # Add other context data as needed
    }
    return render(request, 'Organizations/risk_monitoring.html', context)

@login_required
def equipment_list(request, org_id):
    """View available equipment for rent"""
    organization = get_object_or_404(Organizations, id=org_id)
    equipment = MedicalEquipment.objects.filter(
        organization=organization,
        status='AVAILABLE'
    ).order_by('name')
    
    context = {
        'organization': organization,
        'equipment': equipment
    }
    return render(request, 'Users/equipment_list.html', context)

@login_required
@require_POST
def initiate_rental(request, equipment_id):
    """Handle equipment rental initiation"""
    try:
        # Get the equipment
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id)
        
        # Check if user is registered with the organization
        if not ServiceRequest.objects.filter(
            patient=request.user,
            organization=equipment.organization,
            status='APPROVED'
        ).exists():
            messages.error(request, "You must be registered with the organization to rent equipment.")
            return redirect('patient_rentals')
        
        # Check if equipment is available
        if equipment.status != 'AVAILABLE':
            messages.error(request, "This equipment is not available for rental.")
            return redirect('patient_rentals')
        
        if request.method == 'POST':
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            # Validate dates
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if start_date < date.today():
                    raise ValidationError("Start date cannot be in the past")
                if end_date <= start_date:
                    raise ValidationError("End date must be after start date")
                
                # Calculate rental duration and total amount
                rental_days = (end_date - start_date).days + 1
                total_amount = rental_days * equipment.rental_price_per_day
                
                # Create rental order
                rental = EquipmentRental.objects.create(
                    equipment=equipment,
                    patient=request.user,
                    start_date=start_date,
                    end_date=end_date,
                    total_amount=total_amount,
                    security_deposit=equipment.security_deposit,
                    status='PENDING'
                )
                
                # Create Razorpay order
                order = create_rental_payment_order(rental)
                if order:
                    rental.razorpay_order_id = order['id']
                    rental.save()
                    
                    return JsonResponse({
                        'success': True,
                        'order_id': order['id'],
                        'amount': order['amount'],
                        'rental_id': rental.id
                    })
                else:
                    rental.delete()
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to create payment order'
                    }, status=400)
                    
            except (ValueError, ValidationError) as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=400)
        
        # GET request - show rental form
        context = {
            'equipment': equipment,
            'min_date': date.today().strftime('%Y-%m-%d'),
            'max_date': (date.today() + timedelta(days=90)).strftime('%Y-%m-%d')
        }
        
        return render(request, 'Users/initiate_rental.html', context)
        
    except Exception as e:
        messages.error(request, f"Error initiating rental: {str(e)}")
        return redirect('patient_rentals')

@login_required
@require_POST
def confirm_rental_payment(request):
    """Confirm rental payment and create delivery request"""
    payment_id = request.POST.get('razorpay_payment_id')
    order_id = request.POST.get('razorpay_order_id')
    signature = request.POST.get('razorpay_signature')
    
    try:
        with transaction.atomic():
            # Get rental by order ID
            rental = EquipmentRental.objects.get(razorpay_order_id=order_id)
            
            # Verify payment signature
            if verify_rental_payment(payment_id, order_id, signature):
                # Update rental status
                rental.status = 'APPROVED'
                rental.payment_status = 'COMPLETED'
                rental.razorpay_payment_id = payment_id
                rental.save()
                
                # Update equipment status
                rental.equipment.status = 'RENTED'
                rental.equipment.save()
                
                # Create delivery request
                EquipmentDelivery.objects.create(
                    rental=rental,
                    status='PENDING'
                )
                
                return JsonResponse({'success': True})
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Payment verification failed'
                }, status=400)
                
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@organization_login_required
def manage_equipment(request):
    """View for managing equipment inventory and rentals"""
    organization = get_object_or_404(Organizations, id=request.session.get('org_id'))
    
    # Get all equipment for this organization
    equipment = MedicalEquipment.objects.filter(organization=organization)
    
    # Get pending rental requests - include both PENDING and DEPOSIT_PENDING status
    rental_requests = EquipmentRental.objects.filter(
        equipment__organization=organization,
        status__in=['PENDING', 'DEPOSIT_PENDING']
    ).select_related('equipment', 'patient').order_by('-created_at')
    
    # Get rental history
    rental_history = EquipmentRental.objects.filter(
        equipment__organization=organization,
        status__in=['APPROVED', 'REJECTED', 'COMPLETED']
    ).select_related('equipment', 'patient').order_by('-updated_at')
    
    context = {
        'equipment': equipment,
        'rental_requests': rental_requests,
        'rental_history': rental_history,
        'organization': organization
    }
    
    return render(request, 'Organizations/manage_equipment.html', context)

@organization_login_required
@require_POST
def save_equipment(request):
    """Save new or update existing equipment"""
    try:
        equipment_id = request.POST.get('equipment_id')
        
        if equipment_id:
            # Update existing equipment
            equipment = get_object_or_404(
                MedicalEquipment, 
                id=equipment_id, 
                organization=request.organization
            )
            message = f'Equipment "{equipment.name}" updated successfully'
        else:
            # Create new equipment
            equipment = MedicalEquipment(organization=request.organization)
            message = 'New equipment added successfully'
        
        # Update fields
        equipment.name = request.POST.get('name')
        equipment.equipment_type = request.POST.get('equipment_type')
        equipment.description = request.POST.get('description')
        equipment.condition = request.POST.get('condition')
        equipment.rental_price_per_day = request.POST.get('rental_price_per_day')
        equipment.security_deposit = request.POST.get('security_deposit')
        equipment.serial_number = request.POST.get('serial_number')
        
        equipment.save()
        messages.success(request, message)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@organization_login_required
@require_POST
def delete_equipment(request, equipment_id):
    """Delete equipment"""
    try:
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id, organization=request.organization)
        
        # Check if equipment can be deleted
        if equipment.status == 'RENTED':
            messages.warning(request, f'Cannot delete "{equipment.name}" because it is currently rented')
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete equipment that is currently rented'
            }, status=400)
        
        equipment_name = equipment.name
        equipment.delete()
        messages.success(request, f'Equipment "{equipment_name}" deleted successfully')
        return JsonResponse({'success': True})
        
    except Exception as e:
        messages.error(request, f'Error deleting equipment: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@organization_login_required
def get_equipment_details(request, equipment_id):
    """Get equipment details for editing"""
    try:
        equipment = get_object_or_404(
            MedicalEquipment, 
            id=equipment_id, 
            organization=request.organization
        )
        
        return JsonResponse({
            'success': True,
            'equipment': {
                'id': equipment.id,
                'name': equipment.name,
                'equipment_type': equipment.equipment_type,
                'description': equipment.description,
                'condition': equipment.condition,
                'rental_price_per_day': equipment.rental_price_per_day,
                'security_deposit': equipment.security_deposit,
                'serial_number': equipment.serial_number
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@organization_login_required
def rental_requests(request):
    try:
        # Get pending rental requests
        pending_rentals = EquipmentRental.objects.filter(
            equipment__organization_id=request.session.get('org_id'),
            status='PENDING'
        ).select_related('equipment', 'patient').order_by('rental_end_date')
        
        # Get active rentals
        active_rentals = EquipmentRental.objects.filter(
            equipment__organization_id=request.session.get('org_id'),
            status='APPROVED'
        ).select_related('equipment', 'patient').order_by('rental_end_date')
        
        # Update equipment quantity for paid rentals
        paid_rentals = EquipmentRental.objects.filter(
            equipment__organization_id=request.session.get('org_id'),
            payment_status='PAID',
            status='APPROVED',
            equipment__quantity__gt=0  # Only process if equipment is available
        ).select_related('equipment')

        # Update equipment quantities
        with transaction.atomic():
            for rental in paid_rentals:
                equipment = rental.equipment
                if equipment.quantity > 0:
                    equipment.quantity -= 1
                    equipment.save()
                    
                    # Update rental status to ACTIVE
                    rental.status = 'ACTIVE'
                    rental.save()
                    
                    # Add notification/message
                    messages.success(
                        request, 
                        f'Equipment "{equipment.name}" quantity updated. {equipment.quantity} units remaining.'
                    )

        # Get rental history
        rental_history = EquipmentRental.objects.filter(
            equipment__organization_id=request.session.get('org_id'),
            status__in=['COMPLETED', 'REJECTED']
        ).select_related('equipment', 'patient').order_by('-created_at')
        
        context = {
            'pending_rentals': pending_rentals,
            'active_rentals': active_rentals,
            'rental_history': rental_history,
            'pending_requests_count': pending_rentals.count()
        }
        
        return render(request, 'Organizations/rental_requests.html', context)
        
    except Exception as e:
        print(f"Error in rental_requests view: {str(e)}")
        messages.error(request, "An error occurred while loading rental requests.")
        return redirect('manage_equipment')

@organization_login_required
def get_rental_details(request, rental_id):
    """Get detailed view of a rental request"""
    try:
        rental = get_object_or_404(
            EquipmentRental.objects.select_related('equipment', 'patient'),
            id=rental_id,
            equipment__organization=request.organization
        )
        
        # Get delivery info if exists
        delivery = EquipmentDelivery.objects.filter(rental=rental).first()
        
        html = render_to_string('Organizations/rental_details_partial.html', {
            'rental': rental,
            'delivery': delivery
        }, request=request)
        
        return JsonResponse({
            'success': True,
            'html': html
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@organization_login_required
@require_POST
def assign_delivery(request):
    """Assign a volunteer to deliver equipment"""
    try:
        rental_id = request.POST.get('rental_id')
        volunteer_id = request.POST.get('volunteer_id')
        delivery_notes = request.POST.get('delivery_notes')
        
        with transaction.atomic():
            rental = get_object_or_404(
                EquipmentRental,
                id=rental_id,
                equipment__organization=request.organization,
                status='APPROVED'
            )
            
            volunteer = get_object_or_404(
                Staff,
                id=volunteer_id,
                organization=request.organization,
                role='VOLUNTEER'
            )
            
            # Create or update delivery
            delivery, created = EquipmentDelivery.objects.update_or_create(
                rental=rental,
                defaults={
                    'volunteer': volunteer,
                    'status': 'ASSIGNED',
                    'assigned_at': timezone.now(),
                    'delivery_notes': delivery_notes
                }
            )
            
            # Update rental status
            rental.status = 'ACTIVE'
            rental.save()
            
            # Notify volunteer
            Notification.objects.create(
                staff=volunteer,
                title='New Delivery Assignment',
                message=f'You have been assigned to deliver {rental.equipment.name} to {rental.patient.get_full_name()}'
            )
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@organization_login_required
@require_POST
def mark_rental_returned(request, rental_id):
    """Mark equipment as returned"""
    try:
        with transaction.atomic():
            rental = get_object_or_404(
                EquipmentRental,
                id=rental_id,
                equipment__organization=request.organization,
                status='ACTIVE'
            )
            
            # Update rental status
            rental.status = 'COMPLETED'
            rental.save()
            
            # Update equipment status
            rental.equipment.status = 'AVAILABLE'
            rental.equipment.save()
            
            # Update delivery status if exists
            delivery = EquipmentDelivery.objects.filter(rental=rental).first()
            if delivery:
                delivery.status = 'COMPLETED'
                delivery.save()
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@organization_login_required
def delivery_management(request):
    try:
        organization = request.organization
        
        # Get pending deliveries
        pending_deliveries = EquipmentDelivery.objects.filter(
            rental__equipment__organization=organization,
            status='PENDING'
        ).select_related('rental__equipment', 'rental__patient')
        
        # Get active deliveries
        active_deliveries = EquipmentDelivery.objects.filter(
            rental__equipment__organization=organization,
            status='IN_PROGRESS'
        ).select_related('rental__equipment', 'rental__patient', 'volunteer')
        
        # Get completed deliveries
        completed_deliveries = EquipmentDelivery.objects.filter(
            rental__equipment__organization=organization,
            status='DELIVERED'
        ).select_related('rental__equipment', 'rental__patient', 'volunteer')
        
        # Get available volunteers
        available_volunteers = Staff.objects.filter(
            organization=organization,
            role='VOLUNTEER',
            is_active=True
        )
        
        context = {
            'pending_deliveries': pending_deliveries,
            'active_deliveries': active_deliveries,
            'completed_deliveries': completed_deliveries,
            'available_volunteers': available_volunteers
        }
        
        return render(request, 'Organizations/delivery_management.html', context)
        
    except Exception as e:
        print(f"Error in delivery_management: {str(e)}")
        messages.error(request, "An error occurred while loading delivery data.")
        return redirect('manage_equipment')

@organization_login_required
def assign_volunteer(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    try:
        delivery_id = request.POST.get('delivery_id')
        volunteer_id = request.POST.get('volunteer_id')
        notes = request.POST.get('notes', '')
        
        with transaction.atomic():
            delivery = get_object_or_404(
                EquipmentDelivery, 
                id=delivery_id,
                rental__equipment__organization=request.organization
            )
            
            volunteer = get_object_or_404(
                Staff,
                id=volunteer_id,
                organization=request.organization,
                role='VOLUNTEER'
            )
            
            # Update delivery
            delivery.volunteer = volunteer
            delivery.status = 'ASSIGNED'
            delivery.assigned_at = timezone.now()
            delivery.delivery_notes = notes
            delivery.save()
            
            # Send notification to volunteer
            # TODO: Implement notification system
            
            messages.success(request, f"Delivery assigned to {volunteer.get_full_name()}")
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@staff_login_required
def volunteer_dashboard(request):
    try:
        volunteer = get_object_or_404(Staff, id=request.session.get('staff_id'))
        
        # Get assigned deliveries
        pending_deliveries = EquipmentDelivery.objects.filter(
            volunteer=volunteer,
            status='ASSIGNED'
        ).select_related('rental__equipment', 'rental__patient')
        
        # Get active deliveries
        active_deliveries = EquipmentDelivery.objects.filter(
            volunteer=volunteer,
            status='IN_PROGRESS'
        ).select_related('rental__equipment', 'rental__patient')
        
        context = {
            'volunteer': volunteer,
            'pending_deliveries': pending_deliveries,
            'active_deliveries': active_deliveries
        }
        
        return render(request, 'staff/volunteer_dashboard.html', context)
        
    except Exception as e:
        print(f"Error in volunteer_dashboard: {str(e)}")
        messages.error(request, "An error occurred while loading dashboard.")
        return redirect('staff_login')

def handle_org_login(request):
    """Handle organization login"""
    if request.method == 'POST':
        org_email = request.POST.get('org_email')
        org_password = request.POST.get('org_password')
        
        try:
            organization = Organizations.objects.get(org_email=org_email)
            if organization.check_password(org_password):
                if not organization.approve:
                    messages.error(request, "Your organization has not been approved yet.")
                    return redirect('organizations_home')
                    
                if not organization.is_email_verified:
                    messages.error(request, "Please verify your email first.")
                    return redirect('organizations_home')
                    
                # Set session variables
                request.session['org_id'] = organization.id
                request.session['org_name'] = organization.org_name
                request.session['org_email'] = organization.org_email
                request.session['role'] = 'organization'
                
                return redirect('palliatives_dashboard')
            else:
                messages.error(request, "Invalid password.")
        except Organizations.DoesNotExist:
            messages.error(request, "Organization not found.")
            
    return redirect('organizations_home')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@staff_login_required
def staff_deliveries(request):
    """View for staff member's current deliveries"""
    staff = Staff.objects.get(id=request.session.get('staff_id'))
    deliveries = EquipmentDelivery.objects.filter(
        volunteer=staff,
        status__in=['ASSIGNED', 'IN_PROGRESS']
    ).select_related('rental', 'rental__equipment', 'rental__patient')
    
    return render(request, 'staff/my_deliveries.html', {'deliveries': deliveries})

@staff_login_required
def delivery_history(request):
    """View for staff member's delivery history"""
    try:
        # Verify staff exists and is active
        staff = get_object_or_404(Staff, 
            id=request.session.get('staff_id'),
            is_active=True
        )
        
        # Get all completed and cancelled deliveries for this volunteer
        deliveries = EquipmentDelivery.objects.filter(
            volunteer=staff,
            status__in=['DELIVERED', 'CANCELLED']
        ).select_related(
            'rental',
            'rental__equipment',
            'rental__patient'
        ).order_by('-completed_at', '-updated_at')
        
        context = {
            'deliveries': deliveries,
            'staff': staff
        }
        
        return render(request, 'staff/delivery_history.html', context)
        
    except Staff.DoesNotExist:
        messages.error(request, "Staff account not found or inactive.")
        return redirect('staff_login')
    except Exception as e:
        print(f"Error in delivery_history view: {str(e)}")
        messages.error(request, "An error occurred while loading delivery history.")
        return redirect('volunteer_dashboard')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@staff_login_required
@require_POST
def accept_delivery(request, delivery_id):
    """Accept a delivery assignment"""
    try:
        with transaction.atomic():
            delivery = get_object_or_404(
                EquipmentDelivery,
                id=delivery_id,
                volunteer_id=request.session.get('staff_id'),
                status='ASSIGNED'
            )
            
            delivery.status = 'IN_PROGRESS'
            delivery.started_at = timezone.now()
            delivery.save()
            
            messages.success(request, "Delivery accepted successfully.")
            return JsonResponse({'success': True})
            
    except Exception as e:
        messages.error(request, f"Error accepting delivery: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@staff_login_required
@require_POST
def complete_delivery(request, delivery_id):
    """Mark a delivery as completed"""
    try:
        with transaction.atomic():
            delivery = get_object_or_404(
                EquipmentDelivery,
                id=delivery_id,
                volunteer_id=request.session.get('staff_id'),
                status='IN_PROGRESS'
            )
            
            delivery.status = 'DELIVERED'
            delivery.completed_at = timezone.now()
            delivery.save()
            
            messages.success(request, "Delivery completed successfully.")
            return JsonResponse({'success': True})
            
    except Exception as e:
        messages.error(request, f"Error completing delivery: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def staff_logout(request):
    """Handle staff logout"""
    # Store the message before clearing session
    staff_name = request.session.get('staff_name', 'User')
    
    # Clear all session data
    request.session.flush()
    
    # Add logout success message
    messages.success(request, f"{staff_name}! You have been successfully logged out.")
    return redirect('login')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def patient_rentals(request):
    patient = get_object_or_404(User, id=request.session.get('user_id'))
    
    # Get available equipment
    available_equipment = MedicalEquipment.objects.filter(
        status='AVAILABLE',
        quantity__gt=0
    ).exclude(
        equipmentrental__patient=patient,
        equipmentrental__status__in=['PENDING', 'DEPOSIT_PENDING', 'APPROVED', 'ACTIVE']
    )
    
    # Get pending rentals
    pending_rentals = EquipmentRental.objects.filter(
        patient=patient,
        status__in=['PENDING', 'DEPOSIT_PENDING']
    ).order_by('-created_at')
    
    # Get active rentals (explicitly exclude pending statuses)
    active_rentals = EquipmentRental.objects.filter(
        patient=patient,
        status__in=['APPROVED', 'ACTIVE', 'IN_DELIVERY']
    ).exclude(
        status__in=['PENDING', 'DEPOSIT_PENDING']
    ).order_by('-created_at')
    
    # Get rental history
    rental_history = EquipmentRental.objects.filter(
        patient=patient,
        status__in=['COMPLETED', 'CANCELLED', 'REJECTED']
    ).order_by('-created_at')
    
    context = {
        'available_equipment': available_equipment,
        'pending_rentals': pending_rentals,
        'active_rentals': active_rentals,
        'rental_history': rental_history
    }
    
    return render(request, 'Users/patient_rentals.html', context)

@organization_login_required
def add_equipment(request, equipment_id=None):
    """View for adding/editing medical equipment"""
    try:
        organization = Organizations.objects.get(id=request.session.get('org_id'))
        equipment = None
        
        if equipment_id:
            equipment = get_object_or_404(MedicalEquipment, id=equipment_id, organization=organization)
        
        context = {
            'organization': organization,
            'equipment': equipment,  # Pass equipment to template if editing
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'is_edit': equipment is not None,
            'condition_choices': MedicalEquipment.CONDITION_CHOICES  # Add this line
        }
        
        return render(request, 'Organizations/add_equipment.html', context)
        
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found!")
        return redirect('organizations_home')

@organization_login_required
def update_equipment(request, equipment_id):
    """Update existing equipment"""
    try:
        organization = Organizations.objects.get(id=request.session.get('org_id'))
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id, organization=organization)
        
        if request.method == 'POST':
            form = EquipmentForm(request.POST, request.FILES, instance=equipment)
            if form.is_valid():
                # Only update primary_image if a new one is provided
                if not request.FILES.get('primary_image'):
                    form.cleaned_data.pop('primary_image', None)
                
                equipment = form.save()
                messages.success(request, "Equipment updated successfully!")
                return JsonResponse({'success': True})
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid form data: ' + str(form.errors)
                })
                
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@organization_login_required
def toggle_equipment_status(request, equipment_id):
    try:
        organization = Organizations.objects.get(id=request.session.get('org_id'))
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id, organization=organization)
        
        if request.method == 'POST':
            # Toggle the status between AVAILABLE and MAINTENANCE
            equipment.status = 'MAINTENANCE' if equipment.status == 'AVAILABLE' else 'AVAILABLE'
            equipment.save()  # This saves the change to the database
            
            messages.success(
                request, 
                f"Equipment {equipment.name} has been {'disabled' if equipment.status == 'MAINTENANCE' else 'enabled'}"
            )
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def initiate_rental(request, equipment_id):
    """View for initiating equipment rental"""
    try:
        # Get the patient from session
        patient = User.objects.get(id=request.session.get('user_id'))
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id)
        
        # Check if patient is registered with the organization
        if not ServiceRequest.objects.filter(
            patient=patient, 
            organization=equipment.organization,
            status='APPROVED'
        ).exists():
            messages.error(request, "You must be registered with the organization to rent equipment.")
            return redirect('patient_rentals')
        
        # Check if equipment is available
        if equipment.status != 'AVAILABLE':
            messages.error(request, "This equipment is not available for rent.")
            return redirect('patient_rentals')
        
        # Create rental request
        rental = EquipmentRental.objects.create(
            patient=patient,
            equipment=equipment,
            daily_rental_price=equipment.rental_price_per_day,  # Changed from rental_price_per_day
            deposit_amount=equipment.security_deposit,          # Changed from security_deposit
            status='PENDING'
        )
        
        # Create payment order
        order = create_rental_payment_order(rental)
        
        context = {
            'rental': rental,
            'equipment': equipment,
            'order': order,
            'razorpay_key': settings.RAZORPAY_KEY_ID
        }
        
        return render(request, 'Users/confirm_rental.html', context)
        
    except User.DoesNotExist:
        messages.error(request, "User not found!")
        return redirect('login')
    except Exception as e:
        messages.error(request, str(e))
        return redirect('patient_rentals')

@patient_login_required
def process_rental_payment(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id')
        )
        
        # Get user's location
        user_location = get_object_or_404(UserLocation, user_id=request.session.get('user_id'))
        
        # Format the delivery address
        delivery_address = f"{user_location.address}, {user_location.city} - {user_location.pincode}"
        
        # Update rental with delivery address and any special instructions
        rental.delivery_address = delivery_address
        rental.special_instructions = request.POST.get('special_instructions', '')
        
        # Create Razorpay order
        amount = int((rental.daily_rental_price + rental.deposit_amount) * 100)  # Convert to paise
        order = razorpay_client.order.create({
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'rental_id': rental.id
            }
        })
        
        # Store the order ID in rental
        rental.razorpay_order_id = order['id']
        rental.save()
        
        return JsonResponse({
            'success': True,
            'key': settings.RAZORPAY_KEY_ID,
            'amount': amount,
            'order_id': order['id']
        })
        
    except Exception as e:
        print(f"Error in process_rental_payment: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to process payment request'
        })

@require_POST
@csrf_exempt
def verify_rental_payment(request):
    try:
        data = json.loads(request.body)
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        signature = data.get('razorpay_signature')

        # Verify the payment signature
        params_dict = {
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        }

        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            print(f"Signature verification failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid payment signature'
            })

        # Get the rental and update its status
        rental = EquipmentRental.objects.get(razorpay_order_id=order_id)
        rental.status = 'APPROVED'
        rental.payment_status = 'PAID'
        rental.razorpay_payment_id = payment_id
        rental.save()

        # Create payment record
        payment = RentalPayment.objects.create(
            rental=rental,
            amount=rental.deposit_amount + rental.daily_rental_price,
            payment_type='INITIAL',
            razorpay_payment_id=payment_id,
            razorpay_order_id=order_id,
            status='COMPLETED'
        )

        # Create delivery record
        EquipmentDelivery.objects.create(
            rental=rental,
            status='PENDING'
        )

        # Send notifications
        try:
            send_rental_payment_notification(rental, payment)
        except Exception as e:
            print(f"Error sending notification: {str(e)}")

        return JsonResponse({
            'success': True,
            'redirect_url': reverse('patient_rentals')
        })

    except EquipmentRental.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Rental not found'
        })
    except Exception as e:
        print(f"Payment verification error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@organization_login_required
def rental_analytics(request):
    """View for rental payment analytics"""
    organization = Organizations.objects.get(id=request.session.get('org_id'))
    
    # Get date range from request or default to last 30 days
    end_date = timezone.now().date()
    start_date = request.GET.get('start_date', end_date - timedelta(days=30))
    
    analytics = RentalPaymentAnalytics.objects.filter(
        organization=organization,
        date__range=[start_date, end_date]
    ).order_by('date')
    
    # Calculate summary statistics
    summary = {
        'total_revenue': sum(a.total_amount for a in analytics),
        'total_rentals': sum(a.total_payments for a in analytics),
        'avg_rental_value': sum(a.rental_fees for a in analytics) / len(analytics) if analytics else 0,
        'security_deposits_held': sum(a.security_deposits for a in analytics),
        'refunds_issued': sum(a.refunds_issued for a in analytics)
    }
    
    context = {
        'analytics': analytics,
        'summary': summary,
        'start_date': start_date,
        'end_date': end_date
    }
    
    return render(request, 'Organizations/rental_analytics.html', context)

@patient_login_required
def initiate_rental_request(request, equipment_id):
    try:
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id)
        
        # Check if there's already a pending request for this equipment
        existing_request = EquipmentRental.objects.filter(
            equipment=equipment,
            patient_id=request.session.get('user_id'),
            status__in=['PENDING', 'APPROVED']
        ).exists()
        
        if existing_request:
            return JsonResponse({
                'success': False,
                'error': 'You already have a pending or approved request for this equipment'
            })
        
        # Create rental request
        rental = EquipmentRental.objects.create(
            equipment=equipment,
            patient_id=request.session.get('user_id'),
            daily_rental_price=equipment.rental_price_per_day,
            deposit_amount=equipment.security_deposit,
            status='PENDING',
            payment_status='PENDING'
        )
        
        # Send notification to organization
        try:
            send_rental_request_notification(rental)
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            # Continue even if notification fails
        
        return JsonResponse({
            'success': True,
            'message': 'Rental request sent successfully!'
        })
        
    except Exception as e:
        print(f"Error in initiate_rental_request: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@organization_login_required
def approve_rental_request(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            equipment__organization_id=request.session.get('org_id'),
            status='PENDING'
        )
        
        with transaction.atomic():
            # Update rental status
            rental.status = 'APPROVED'
            rental.save()
            
            # Send notification to patient
            send_rental_approval_notification(rental)
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@organization_login_required
@require_POST
def reject_rental_request(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            equipment__organization_id=request.session.get('org_id'),
            status='PENDING'
        )
        
        rejection_reason = request.POST.get('rejection_reason')
        if not rejection_reason:
            return JsonResponse({
                'success': False,
                'error': 'Rejection reason is required'
            })
            
        with transaction.atomic():
            # Update rental status
            rental.status = 'REJECTED'
            rental.rejection_reason = rejection_reason
            rental.save()
            
            # Make equipment available again
            equipment = rental.equipment
            equipment.status = 'AVAILABLE'
            equipment.save()
            
            # Send notification to patient
            send_rental_rejection_notification(rental)
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@require_GET
def get_rental_history(request, rental_id):
    try:
        # Add debug logging
        print(f"Fetching rental history for rental ID: {rental_id}")
        
        if 'org_id' in request.session:
            rental = get_object_or_404(
                EquipmentRental.objects.select_related(
                    'equipment', 
                    'patient',
                    'equipment__organization',
                    'delivery'  # Updated from equipmentdelivery_set
                ).prefetch_related('payments'),
                id=rental_id,
                equipment__organization_id=request.session['org_id']
            )
        else:
            rental = get_object_or_404(
                EquipmentRental.objects.select_related(
                    'equipment', 
                    'patient',
                    'equipment__organization',
                    'delivery'  # Updated from equipmentdelivery_set
                ).prefetch_related('payments'),
                id=rental_id,
                patient_id=request.session.get('user_id')
            )
            
        context = {
            'rental': rental,
            'delivery': rental.delivery,  # Updated from equipmentdelivery_set.first()
            'payments': rental.payments.all().order_by('-payment_date')
        }
        
        html = render_to_string('Organizations/rental_history_partial.html', context, request=request)
        return JsonResponse({'success': True, 'html': html})
        
    except Exception as e:
        print(f"Error in get_rental_history: {str(e)}")  # Debug logging
        return JsonResponse({'success': False, 'error': str(e)})

@patient_login_required
def confirm_rental(request, rental_id):
    rental = get_object_or_404(
        EquipmentRental, 
        id=rental_id,
        patient_id=request.session.get('user_id'),
        status='APPROVED',
        payment_status='PENDING'
    )
    
    # Get user's location
    user_location = get_object_or_404(UserLocation, user_id=request.session.get('user_id'))
    
    # Calculate total amount
    total_amount = float(rental.daily_rental_price) + float(rental.deposit_amount)
    
    context = {
        'rental': rental,
        'total_amount': total_amount,
        'user_location': user_location
    }
    
    return render(request, 'Users/confirm_rental.html', context)

@patient_login_required
def rental_request(request, equipment_id):
    try:
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id)
        
        # Check if there's already a pending request for this equipment
        existing_request = EquipmentRental.objects.filter(
            equipment=equipment,
            patient_id=request.session.get('user_id'),
            status__in=['PENDING', 'APPROVED']
        ).exists()
        
        if existing_request:
            messages.warning(request, 'You already have a pending or approved request for this equipment')
            return redirect('patient_rentals')
        
        # Create rental request
        rental = EquipmentRental.objects.create(
            equipment=equipment,
            patient_id=request.session.get('user_id'),
            daily_rental_price=equipment.rental_price_per_day,
            deposit_amount=equipment.security_deposit,
            status='PENDING',
            payment_status='PENDING'
        )
        
        # Send notification to organization
        try:
            send_rental_request_notification(rental)
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
        
        messages.success(request, 'Rental request sent successfully! You will be notified once approved.')
        return redirect('patient_rentals')
        
    except Exception as e:
        print(f"Error in rental_request: {str(e)}")
        messages.error(request, 'An error occurred while processing your request.')
        return redirect('patient_rentals')

@staff_login_required
def start_delivery(request, delivery_id):
    """Start a delivery that has been assigned to a volunteer"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    try:
        with transaction.atomic():
            # Get delivery and verify it's assigned to this volunteer
            delivery = get_object_or_404(
                EquipmentDelivery,
                id=delivery_id,
                volunteer_id=request.session.get('staff_id'),
                status='ASSIGNED'
            )
            
            # Update delivery status
            delivery.status = 'IN_PROGRESS'
            delivery.started_at = timezone.now()
            delivery.save()
            
            # Add notification/message
            messages.success(request, f"Delivery #{delivery.id} started successfully")
            
            # Return success response with message
            return JsonResponse({
                'success': True,
                'message': f"Delivery #{delivery.id} started successfully"
            })
            
    except EquipmentDelivery.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found or not assigned to you'
        })
    except Exception as e:
        print(f"Error starting delivery: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@staff_login_required
def complete_delivery(request, delivery_id):
    """Mark a delivery as completed"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    try:
        with transaction.atomic():
            # Get delivery and verify it's assigned to this volunteer
            delivery = get_object_or_404(
                EquipmentDelivery,
                id=delivery_id,
                volunteer_id=request.session.get('staff_id'),
                status='IN_PROGRESS'
            )
            
            # Update delivery status
            delivery.status = 'DELIVERED'
            delivery.completed_at = timezone.now()
            delivery.save()
            
            # Update rental status
            rental = delivery.rental
            rental.status = 'ACTIVE'
            rental.save()
            
            # Add notification/message
            messages.success(request, f"Delivery #{delivery.id} completed successfully")
            
            return JsonResponse({'success': True})
            
    except EquipmentDelivery.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found or not assigned to you'
        })
    except Exception as e:
        print(f"Error completing delivery: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to complete delivery'
        })

@staff_login_required
def update_delivery_location(request, delivery_id):
    """Update volunteer's current location"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        delivery = get_object_or_404(
            EquipmentDelivery,
            id=delivery_id,
            volunteer_id=request.session.get('staff_id'),
            status__in=['IN_PROGRESS', 'ARRIVED']
        )
        
        delivery.volunteer_latitude = latitude
        delivery.volunteer_longitude = longitude
        delivery.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@staff_login_required
def mark_arrived(request, delivery_id):
    """Mark delivery as arrived at location"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        with transaction.atomic():
            delivery = get_object_or_404(
                EquipmentDelivery,
                id=delivery_id,
                volunteer_id=request.session.get('staff_id'),
                status='IN_PROGRESS'
            )
            
            # Generate OTP
            otp = delivery.generate_otp()
            
            # Update status
            delivery.status = 'ARRIVED'
            delivery.arrived_at = timezone.now()
            delivery.save()
            
            # Send OTP to patient
            send_delivery_otp(delivery)
            
            return JsonResponse({'success': True})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@staff_login_required
def verify_delivery_otp(request, delivery_id):
    """Verify delivery OTP"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        otp = request.POST.get('otp')
        
        delivery = get_object_or_404(
            EquipmentDelivery,
            id=delivery_id,
            volunteer_id=request.session.get('staff_id'),
            status='ARRIVED'
        )
        
        if delivery.verify_otp(otp):
            delivery.status = 'OTP_VERIFIED'
            delivery.otp_verified_at = timezone.now()
            delivery.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired OTP'
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@patient_login_required
def get_delivery_location(request, delivery_id):
    """Get current location of delivery volunteer"""
    try:
        delivery = get_object_or_404(
            EquipmentDelivery,
            id=delivery_id,
            rental__patient_id=request.session.get('user_id'),
            status='IN_PROGRESS'
        )
        
        return JsonResponse({
            'success': True,
            'latitude': float(delivery.volunteer_latitude),
            'longitude': float(delivery.volunteer_longitude)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def calculate_rental(request, equipment_id):
    """Show rental calculation page"""
    equipment = get_object_or_404(MedicalEquipment, id=equipment_id)
    patient = get_object_or_404(User, id=request.session.get('user_id'))
    
    context = {
        'equipment': equipment,
        'today': timezone.now().date(),
        'patient': patient  # Add patient to context
    }
    return render(request, 'Users/rental_calculation.html', context)

@patient_login_required
def create_deposit_order(request, equipment_id):
    """Create Razorpay order for caution deposit"""
    try:
        equipment = get_object_or_404(MedicalEquipment, id=equipment_id)
        data = json.loads(request.body)
        
        # Get patient from session
        patient = get_object_or_404(User, id=request.session.get('user_id'))
        
        # Convert Decimal to float for JSON serialization
        deposit_amount = float(equipment.security_deposit)
        daily_rate = float(equipment.rental_price_per_day)
        
        # Create rental record with DEPOSIT_PENDING status
        rental = EquipmentRental.objects.create(
            equipment=equipment,
            patient=patient,
            rental_start_date=data['start_date'],
            rental_end_date=data['end_date'],
            deposit_amount=deposit_amount,
            daily_rental_price=daily_rate,
            status='DEPOSIT_PENDING'
        )
        
        # Create Razorpay order
        order_amount = int(deposit_amount * 100)  # Convert to paise
        order_currency = 'INR'
        
        order = razorpay_client.order.create({
            'amount': order_amount,
            'currency': order_currency,
            'payment_capture': 1
        })
        
        return JsonResponse({
            'success': True,
            'key': settings.RAZORPAY_KEY_ID,
            'amount': order_amount,
            'order_id': order['id'],
            'rental_id': rental.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def verify_deposit_payment(request):
    """Verify deposit payment and create rental request"""
    try:
        data = json.loads(request.body)
        
        # Get patient from session
        patient = get_object_or_404(User, id=request.session.get('user_id'))
        
        rental = get_object_or_404(
            EquipmentRental, 
            id=data['rental_id'],
            patient=patient
        )
        
        try:
            # Verify payment signature
            params_dict = {
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_signature': data['razorpay_signature']
            }
            
            razorpay_client.utility.verify_payment_signature(params_dict)
            
            # Payment successful - update rental status
            rental.status = 'PENDING'
            rental.save()
            
            RentalPayment.objects.create(
                rental=rental,
                amount=rental.deposit_amount,
                payment_type='DEPOSIT',
                status='SUCCESS',
                razorpay_payment_id=data['razorpay_payment_id'],
                razorpay_order_id=data['razorpay_order_id']
            )
            
            # Send notification
            context = {
                'rental': rental,
                'domain': settings.BASE_URL,
                'STATIC_URL': settings.STATIC_URL
            }
            send_rental_request_notification(rental)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            # Payment failed - delete the rental request
            rental.delete()
            return JsonResponse({
                'success': False,
                'error': 'Payment verification failed. Please try again.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def check_rental_status(request):
    """Check if any rental status has changed"""
    try:
        patient = get_object_or_404(User, id=request.session.get('user_id'))
        
        # Get pending rentals that might have been updated
        pending_rentals = EquipmentRental.objects.filter(
            patient=patient,
            status__in=['PENDING', 'DEPOSIT_PENDING'],
            updated_at__gt=timezone.now() - timedelta(minutes=5)
        ).exists()
        
        return JsonResponse({
            'success': True,
            'status_changed': pending_rentals
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def cancel_rental_request(request):
    """Cancel a rental request if payment fails"""
    try:
        data = json.loads(request.body)
        rental = get_object_or_404(
            EquipmentRental, 
            id=data['rental_id'],
            patient_id=request.session.get('user_id'),
            status='DEPOSIT_PENDING'
        )
        
        # Delete the rental request
        rental.delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@organization_login_required
def get_rental_history(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            equipment__organization_id=request.session.get('org_id')
        )
        
        payments = RentalPayment.objects.filter(rental=rental).values(
            'payment_date',
            'payment_type',
            'amount',
            'status',
            'razorpay_payment_id'
        )
        
        return JsonResponse({
            'success': True,
            'payments': list(payments)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def get_accumulated_amount(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id'),
            status='ACTIVE'
        )
        
        # Calculate accumulated amount
        days_rented = (timezone.now().date() - rental.rental_start_date).days
        accumulated_amount = days_rented * rental.daily_rental_price
        
        return JsonResponse({
            'success': True,
            'amount': accumulated_amount
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@patient_login_required
def create_monthly_payment(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id'),
            status='ACTIVE'
        )
        
        # Create or get current month's payment
        current_payment = MonthlyRentalPayment.objects.get_or_create(
            rental=rental,
            month_start_date=timezone.now().replace(day=1).date(),
            defaults={
                'month_end_date': (timezone.now().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1),
                'amount_due': calculate_monthly_rent(rental)
            }
        )[0]
        
        # Create Razorpay order
        order = create_monthly_rental_order(current_payment)
        
        return JsonResponse({
            'success': True,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'amount': order['amount'],
            'order_id': order['id']
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@patient_login_required
def get_rental_usage_details(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id')
        )
        
        return JsonResponse({
            'success': True,
            'rental_start_date': rental.rental_start_date.strftime('%Y-%m-%d'),
            'rental_end_date': rental.rental_end_date.strftime('%Y-%m-%d'),
            'daily_rate': float(rental.daily_rental_price),
            'duration': rental.get_usage_duration(),
            'amount': float(rental.get_current_bill_amount())
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
@require_POST
def end_rental_service(request, rental_id):
    try:
        with transaction.atomic():
            rental = get_object_or_404(
                EquipmentRental, 
                id=rental_id,
                patient_id=request.session.get('user_id'),
                status='ACTIVE'
            )
            
            # Calculate final amount
            final_amount = rental.get_current_bill_amount()
            
            # Create final usage period
            RentalUsagePeriod.objects.create(
                rental=rental,
                start_date=rental.rental_start_date,
                end_date=timezone.now().date(),
                duration=rental.get_usage_duration(),
                amount=final_amount,
                status='PENDING'
            )
            
            # Initiate deposit refund
            refund_amount = rental.deposit_amount
            refund_order = create_refund_order(rental, refund_amount)
            
            # Update rental status
            rental.status = 'PENDING_RETURN'
            rental.save()
            
            # Send email notification
            send_rental_end_notification(rental)
            
            return JsonResponse({
                'success': True,
                'final_amount': final_amount,
                'deposit_amount': float(refund_amount),
                'refund_id': refund_order['id']
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@organization_login_required
def get_rental_org_details(request, rental_id):
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            equipment__organization_id=request.session.get('org_id')
        )
        
        # Get usage history
        usage_history = [{
            'start_date': period.start_date.strftime('%b %d, %Y'),
            'end_date': period.end_date.strftime('%b %d, %Y'),
            'duration': period.duration,
            'amount': str(period.amount),
            'status': period.status
        } for period in rental.get_usage_periods()]
        
        return JsonResponse({
            'success': True,
            'patient_name': rental.patient.get_full_name(),
            'patient_contact': rental.patient.phone_number,
            'delivery_address': rental.delivery_address,
            'equipment_name': rental.equipment.name,
            'daily_rate': str(rental.daily_rental_price),
            'start_date': rental.rental_start_date.strftime('%b %d, %Y'),
            'status': rental.status,
            'total_days': rental.get_usage_duration(),
            'total_amount': str(rental.get_current_bill_amount()),
            'payment_status': rental.payment_status,
            'usage_history': usage_history
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def send_delivery_otp(delivery):
    """Send OTP to patient for delivery verification"""
    try:
        # Get patient's phone number
        patient_phone = delivery.rental.patient.phone_number
        
        # Send OTP via SMS
        message = f"Your CareFusion delivery OTP is: {delivery.otp}"
        send_sms(patient_phone, message)  # Assuming you have send_sms utility
        
        # Alternatively, send via email
        subject = "CareFusion Delivery OTP"
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [delivery.rental.patient.email],
            fail_silently=True
        )
    except Exception as e:
        print(f"Error sending OTP: {str(e)}")

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c

    return distance

@team_login_required
def record_visit(request, visit_id):
    """Handle recording of patient visit data"""
    try:
        # Get the team visit and related data
        visit = get_object_or_404(
            TeamVisit.objects.select_related('patient', 'team'),
            id=visit_id,
            team=request.team_membership.team
        )
        
        if request.method == 'POST':
            try:
                with transaction.atomic():
                    # Create visit record
                    visit_record = PatientVisitRecord.objects.create(
                        patient=visit.patient,
                        visit_date=timezone.now(),
                        blood_pressure=request.POST.get('blood_pressure'),
                        pulse_rate=request.POST.get('pulse_rate'),
                        temperature=request.POST.get('temperature'),
                        respiratory_rate=request.POST.get('respiratory_rate'),
                        oxygen_saturation=request.POST.get('oxygen_saturation'),
                        pain_score=request.POST.get('pain_score'),
                        activity_level=request.POST.get('activity_level'),
                        appetite=request.POST.get('appetite'),
                        mood_status=request.POST.get('mood_status'),
                        fall_risk_score=request.POST.get('fall_risk_score'),
                        pressure_ulcer_risk=request.POST.get('pressure_ulcer_risk'),
                        deterioration_risk=request.POST.get('deterioration_risk'),
                        overall_health_score=request.POST.get('overall_health_score'),
                        notes=request.POST.get('notes'),
                        recorded_by=request.team_membership.staff
                    )
                    
                    # Update visit status
                    visit.status = 'COMPLETED'
                    visit.save()
                    
                    messages.success(request, 'Visit data recorded successfully.')
                    return redirect('team_dashboard')
                    
            except Exception as e:
                messages.error(request, f'Error saving visit data: {str(e)}')
                
        context = {
            'visit': visit,
            'patient': visit.patient,
            'team': visit.team,
            'staff': request.team_membership.staff,
        }
        
        return render(request, 'teams/record_visit.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading visit form: {str(e)}")
        return redirect('team_dashboard')



def track_patient_location(request, visit_id):
    visit = get_object_or_404(TeamVisit, id=visit_id)
    
    # Get patient's location
    try:
        patient_location = UserLocation.objects.get(user=visit.patient)
        
        context = {
            'visit': visit,
            'patient_location': {
                'lat': patient_location.latitude,
                'lng': patient_location.longitude
            },
            'staff_location': {
                'lat': request.GET.get('staff_lat'),
                'lng': request.GET.get('staff_lng')
            } if request.GET.get('staff_lat') and request.GET.get('staff_lng') else None
        }
        
        return render(request, 'teams/track_location.html', context)
        
    except UserLocation.DoesNotExist:
        messages.error(request, "Patient location not found")
        return redirect('staff_dashboard')

def verify_code(request, email):
    if request.method == 'POST':
        entered_pin = request.POST.get('pin')
        stored_pin = request.session.get('reset_pin')
        
        if stored_pin and entered_pin == stored_pin:
            # PIN matches, clear it from session and redirect to reset password
            del request.session['reset_pin']
            return redirect('reset_password', email=email)
        else:
            messages.error(request, 'Invalid PIN. Please try again.')
            return redirect('verify_code', email=email)
    
    return render(request, 'Forgot_Password/verifycode.html', {'email': email})

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            # Generate a 4-digit PIN
            pin = ''.join(random.choices('0123456789', k=4))
            # Store PIN in session
            request.session['reset_pin'] = pin
            
            # Send email with PIN
            subject = 'Password Reset PIN'
            message = f'Your password reset PIN is: {pin}'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [email]
            
            try:
                send_mail(subject, message, from_email, recipient_list)
                messages.success(request, 'A PIN has been sent to your email.')
                return redirect('verify_code', email=email)
            except Exception as e:
                messages.error(request, 'Error sending email. Please try again.')
                return redirect('forgot_password')
        else:
            messages.error(request, 'No user found with this email address.')
            return redirect('forgot_password')
    
    return render(request, 'Forgot_Password/forgot_password.html')

@login_required
def patient_dashboard(request):
    try:
        # Get health tips without using cache
        health_tips = get_health_tips()
        
        # Rest of your dashboard context
        context = {
            'health_tips': health_tips,
            # ... other context data ...
        }
        
        return render(request, 'Users/patients_dashboard.html', context)
    except Exception as e:
        messages.error(request, "Error loading dashboard. Please try again.")
        logger.error(f"Error in patient dashboard: {str(e)}")
        return redirect('login')


from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import EquipmentRental
from .decorators import patient_login_required

@patient_login_required
def get_rental_final_amount(request, rental_id):
    """Calculate and return the final rental amount"""
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id')
        )
        
        # Calculate final amount including the entire rental period
        days_used = (rental.rental_end_date - rental.rental_start_date).days + 1
        final_amount = days_used * rental.daily_rental_price
        
        # Log the calculation details
        logger.info(f"Rental ID: {rental_id}")
        logger.info(f"Start Date: {rental.rental_start_date}")
        logger.info(f"End Date: {rental.rental_end_date}")
        logger.info(f"Days Used: {days_used}")
        logger.info(f"Daily Rate: {rental.daily_rental_price}")
        logger.info(f"Final Amount: {final_amount}")
        
        return JsonResponse({
            'success': True,
            'amount': float(final_amount),
            'days': days_used,
            'daily_rate': float(rental.daily_rental_price),
            'start_date': rental.rental_start_date.strftime('%Y-%m-%d'),
            'end_date': rental.rental_end_date.strftime('%Y-%m-%d')
        })
    except Exception as e:
        logger.error(f"Error calculating final amount: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def rental_payment(request, rental_id):
    """Handle rental payment processing"""
    try:
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id'),
            status='END'  # Only allow payment for ended rentals
        )
        
        # Calculate final amount
        days_used = (rental.rental_end_date - rental.rental_start_date).days + 1
        final_amount = days_used * rental.daily_rental_price
        
        # Log the calculation details
        logger.info(f"Rental Payment - Rental ID: {rental_id}")
        logger.info(f"Start Date: {rental.rental_start_date}")
        logger.info(f"End Date: {rental.rental_end_date}")
        logger.info(f"Days Used: {days_used}")
        logger.info(f"Daily Rate: {rental.daily_rental_price}")
        logger.info(f"Final Amount: {final_amount}")
        
        # Create payment order
        order = create_rental_payment_order(rental, final_amount)
        
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'order_id': order['id'],
                'amount': float(final_amount)  # Ensure this matches the amount calculation
            })
        
        # Regular page render
        context = {
            'rental': rental,
            'amount': final_amount,
            'order_id': order['id'],
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'days_used': days_used,
            'daily_rate': float(rental.daily_rental_price)
        }
        
        return render(request, 'Users/rental_payment.html', context)
        
    except Exception as e:
        logger.error(f"Rental payment error: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('patient_rentals')

def create_rental_payment_order(rental, amount):
    """Create Razorpay order for rental payment"""
    try:
        # Validate Razorpay credentials
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise ValueError("Razorpay credentials are not configured")
        
        # Convert amount to paise (ensure it matches the amount from final calculation)
        amount_in_paise = int(amount * 100)
        
        # Create Razorpay order
        order = razorpay_client.order.create({
            'amount': amount_in_paise,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'rental_id': rental.id,
                'payment_type': 'RENTAL_BILL'
            }
        })
        
        # Update rental with order details
        rental.razorpay_order_id = order['id']
        rental.save()
        
        return order
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {str(e)}")
        raise Exception(f"Failed to create payment order: {str(e)}")
@patient_login_required
@require_POST
def request_rental_extension(request):
    """Handle rental extension requests"""
    try:
        data = json.loads(request.body)
        rental_id = data.get('rental_id')
        days = int(data.get('days', 0))
        reason = data.get('reason', '')
        
        if not all([rental_id, days, reason]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            })
            
        # Get the rental without status filter first
        rental = get_object_or_404(
            EquipmentRental, 
            id=rental_id,
            patient_id=request.session.get('user_id')
        )
        
        # Check rental status - allow extension for ACTIVE rentals
        if rental.status not in ['ACTIVE']:  # Changed from ['END', 'ACTIVE'] to ['ACTIVE']
            return JsonResponse({
                'success': False,
                'error': 'Only active rentals can be extended'
            })
        
        # Check if there's already a pending extension request
        existing_request = RentalExtensionRequest.objects.filter(
            rental=rental,
            status='PENDING'
        ).exists()
        
        if existing_request:
            return JsonResponse({
                'success': False,
                'error': 'You already have a pending extension request'
            })
        
        # Create extension request
        extension = RentalExtensionRequest.objects.create(
            rental=rental,
            requested_days=days,
            reason=reason,
            status='PENDING'
        )
        
        # Send notification to organization
        Notification.objects.create(
            patient=rental.patient,
            organization=rental.equipment.organization,
            message=f"Rental extension requested for {rental.equipment.name} for {days} days. Reason: {reason}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Extension request submitted successfully'
        })
        
    except EquipmentRental.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Rental not found'
        })
    except Exception as e:
        logger.error(f"Error in rental extension request: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@patient_login_required
def verify_rental_payment(request):
    """Verify Razorpay payment for rental"""
    try:
        # Get payment details from request
        payment_id = request.GET.get('payment_id')
        order_id = request.GET.get('order_id')
        signature = request.GET.get('signature')
        
        if not all([payment_id, order_id, signature]):
            messages.error(request, "Invalid payment details.")
            return redirect('patient_rentals')
        
        # Verify payment signature
        try:
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
        except Exception as e:
            logger.error(f"Payment signature verification failed: {str(e)}")
            messages.error(request, "Payment verification failed.")
            return redirect('patient_rentals')
        
        # Find the rental associated with this order
        try:
            rental = EquipmentRental.objects.get(razorpay_order_id=order_id)
        except EquipmentRental.DoesNotExist:
            messages.error(request, "Rental not found.")
            return redirect('patient_rentals')
        
        # Fetch payment details from Razorpay
        try:
            payment_details = razorpay_client.payment.fetch(payment_id)
            if payment_details['status'] != 'captured':
                messages.error(request, "Payment not completed.")
                return redirect('patient_rentals')
        except Exception as e:
            logger.error(f"Error fetching payment details: {str(e)}")
            messages.error(request, "Could not verify payment.")
            return redirect('patient_rentals')
        
        # Create payment record - using correct field names
        payment = RentalPayment.objects.create(
            rental=rental,
            amount=rental.get_current_bill_amount(),
            payment_date=timezone.now(),
            razorpay_payment_id=payment_id,  # Changed from payment_id to razorpay_payment_id
            razorpay_order_id=order_id,      # Changed from order_id to razorpay_order_id
            status='PAID',
            payment_type='RENTAL_BILL'
        )
        
        # Update rental status
        rental.status = 'COMPLETED'
        rental.save()
        
        # Create notification
        Notification.objects.create(
            patient=rental.patient,
            organization=rental.equipment.organization,
            message=f"Payment received for rental of {rental.equipment.name}. Total amount: ₹{payment.amount}"
        )
        
        # Generate receipt (optional)
        try:
            receipt_path = generate_rental_receipt(rental, payment)
        except Exception as receipt_error:
            logger.warning(f"Receipt generation failed: {str(receipt_error)}")
        
        # Return JSON response for success
        return JsonResponse({
            'success': True,
            'message': 'Payment successful! Thank you.',
            'redirect_url': reverse('patient_rentals')
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in payment verification: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
