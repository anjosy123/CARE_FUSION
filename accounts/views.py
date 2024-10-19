from django.shortcuts import render,redirect,get_object_or_404
from django.utils.html import strip_tags
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import logout, get_user_model
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib.auth.hashers import check_password, make_password
from django.views.decorators.cache import cache_control, never_cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST
from care_fusion import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
import random, logging, os, string
from django.utils import timezone
from .models import Organizations,Contact,ServiceRequest,Service,Staff,PatientAssignment,Prescription,Appointment
from .forms import ServiceRequestForm,ServiceForm,StaffForm,PatientAssignmentForm,PrescriptionForm,AppointmentForm
from django.contrib.auth import get_user_model
from .utils import send_verification_email, send_appointment_email
from django.db.models import Q
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.decorators import login_required
from .models import Staff, Notification, Message
import uuid

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
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')
    # Add nurse-specific logic here
    return render(request, 'staff/nurse_dashboard.html')


def volunteer_dashboard(request):
    if request.session.get('role') != 'staff' or Staff.objects.get(id=request.session.get('staff_id')).role != 'VOLUNTEER':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('login')
    # Add volunteer-specific logic here
    return render(request, 'staff/volunteer_dashboard.html')

def service_list(request):
    # Check if the organization is logged in via session
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('org_login')  # Redirect to your organization login page

    org_id = request.session['org_id']
    
    try:
        organization = Organizations.objects.get(id=org_id)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('org_login')

    services = Service.objects.filter(organization=organization)
    return render(request, 'Organizations/service_list.html', {'services': services, 'org_name': organization.org_name})

def service_create(request):
    # Check if the organization is logged in via session
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('org_login')  # Redirect to your organization login page

    org_id = request.session['org_id']
    
    try:
        organization = Organizations.objects.get(id=org_id)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('org_login')

    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.organization = organization
            service.save()
            messages.success(request, 'Service created successfully.')
            return redirect('service_list')
    else:
        form = ServiceForm()

    return render(request, 'Organizations/service_form.html', {'form': form, 'org_name': organization.org_name})

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
    if request.session.has_key('user_id'):
        return render(request, 'Admin/admin.html')
    else:
        return redirect('login')

from django.db.models import Q


# User = get_user_model()

# ser = get_user_model()

def handlelogin(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("pass1")

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

    # Check if the request is for the home page
    if request.GET.get('view') == 'home':
        return render(request, 'Users/patient_home.html')

    query = request.GET.get('q', '')
    if query:
        organizations = Organizations.objects.filter(org_name__icontains=query, approve=1)
    else:
        organizations = Organizations.objects.filter(approve=1)
        
    user_id = request.session['user_id']
    service_requests = ServiceRequest.objects.filter(patient_id=user_id).order_by('-created_at')
    
    patient = get_object_or_404(User, id=user_id)
    assignments = PatientAssignment.objects.filter(patient=patient, is_active=True)
    
    prescriptions = Prescription.objects.filter(patient_assignment__in=assignments).order_by('-start_date')
    
    # Split appointments into booked and available
    all_appointments = Appointment.objects.filter(patient_assignment__in=assignments).order_by('date_time')
    booked_appointments = all_appointments.filter(status='BOOKED')
    available_appointments = all_appointments.filter(status='AVAILABLE')
    
    medical_history = []
    for assignment in assignments:
        if assignment.medical_history:
            medical_history.append({
                'organization': assignment.organization,
                'history': assignment.medical_history
            })
    
    # Fetch notifications for the current user
    notifications = Notification.objects.filter(user_id=user_id).order_by('-created_at')[:5]

    context = {
        'organizations': organizations,
        'query': query,
        'service_requests': service_requests,
        'prescriptions': prescriptions,
        'booked_appointments': booked_appointments,
        'available_appointments': available_appointments,
        'medical_history': medical_history,
        'notifications': notifications,
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
            'recent_assignments_html': render_to_string('Organizations/recent_assignments_partial.html', context),
            'pending_requests_html': render_to_string('Organizations/pending_requests_partial.html', context),
            'approved_requests_html': render_to_string('Organizations/approved_requests_partial.html', context),
            'rejected_requests_html': render_to_string('Organizations/rejected_requests_partial.html', context),
        })
    
    # Render full page for non-AJAX requests
    return render(request, 'Organizations/palliatives_dashboard.html', context)

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
                user=updated_appointment.patient_assignment.patient,
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
    return render(request, 'staff/reschedule_appointment.html', context)

    
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
            user=appointment.patient_assignment.patient,
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

def get_dashboard_context(organization):
    return {
        'organization': organization,
        'staff_count': Staff.objects.filter(organization=organization).count(),
        'assigned_patients_count': PatientAssignment.objects.filter(organization=organization, is_active=True).count(),
        'pending_requests': ServiceRequest.objects.filter(organization=organization, status='PENDING').order_by('-created_at'),
        'approved_requests': ServiceRequest.objects.filter(organization=organization, status='APPROVED').order_by('-created_at')[:5],
        'rejected_requests': ServiceRequest.objects.filter(organization=organization, status='REJECTED').order_by('-created_at')[:5],
        'recent_assignments': PatientAssignment.objects.filter(organization=organization, is_active=True).order_by('-assigned_date')[:5],
    }
    

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
    request.session.delete()
    logout(request)
    return redirect('login')

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

# @login_required
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
    
    send_mail(subject, message, from_email, recipient_list)
    
    
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
            form = StaffForm(request.POST, request.FILES)
            if form.is_valid():
                staff = form.save(commit=False)
                staff.organization = organization
                staff.is_active = False  # Staff is inactive until email is confirmed
                staff.username = staff.email  # Set username to email
                temp_password = get_random_string(12)  # Generate a temporary password
                staff.set_password(temp_password)  # Set the temporary password
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
        else:
            form = StaffForm()
        
        context = {
            'form': form,
            'organization': organization,
        }
        return render(request, 'Organizations/add_staff.html', context)
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
    
def edit_staff(request, staff_id):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
        staff = get_object_or_404(Staff, id=staff_id, organization=organization)
        if request.method == 'POST':
            form = StaffForm(request.POST, request.FILES, instance=staff)
            if form.is_valid():
                form.save()
                messages.success(request, 'Staff updated successfully')
                return redirect('staff_list')
        else:
            form = StaffForm(instance=staff)
        
        context = {
            'form': form,
            'staff': staff,
            'organization': organization,
        }
        return render(request, 'Organizations/edit_staff.html', context)
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')


def toggle_staff_status(request, staff_id):
    if 'org_id' not in request.session:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')
    
    org_id = request.session['org_id']
    try:
        organization = Organizations.objects.get(id=org_id)
        staff = get_object_or_404(Staff, id=staff_id, organization=organization)
        staff.is_active = not staff.is_active
        staff.save()
        status = "activated" if staff.is_active else "deactivated"
        messages.success(request, f'Staff {status} successfully')
        return redirect('staff_list')
    except Organizations.DoesNotExist:
        messages.error(request, "Organization not found. Please log in again.")
        return redirect('login')

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
    org_name = request.session['org_name']
    
    try:
        organization = Organizations.objects.get(id=org_id, org_name=org_name)
        
        if request.method == 'POST':
            form = PatientAssignmentForm(request.POST)
            if form.is_valid():
                assignment = form.save(commit=False)
                assignment.organization = organization
                
                # Check if the patient has an approved service request for this organization
                patient = form.cleaned_data['patient']
                if not ServiceRequest.objects.filter(patient=patient, organization=organization, status='APPROVED').exists():
                    messages.error(request, "Invalid patient selection. The patient must have an approved service request.")
                    return redirect('assign_patient')
                
                assignment.save()
                messages.success(request, 'Patient assigned successfully.')
                return redirect('patient_assignment_list')
        else:
            form = PatientAssignmentForm()
        
        # Get patients with approved service requests for this organization
        assigned_patients = PatientAssignment.objects.filter(organization=organization, is_active=True).values_list('patient', flat=True)
        unassigned_patients = User.objects.filter(
            Q(is_superuser=False) & 
            Q(is_active=True) & 
            Q(is_email_verified=True) &
            Q(service_requests__organization=organization) &
            Q(service_requests__status='APPROVED')
        ).exclude(id__in=assigned_patients).distinct()
        
        # Get staff members associated with this organization
        staff_members = Staff.objects.filter(
            organization=organization,
            is_active=True
        )

        context = {
            'form': form,
            'organization': organization,
            'unassigned_patients': unassigned_patients,
            'staff_members': staff_members,
        }
        return render(request, 'Organizations/assign_patient.html', context)
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

def manage_prescriptions(request, assignment_id):
    # Instead of looking up by user, we'll use the staff_id from the session
    staff_id = request.session.get('staff_id')
    if not staff_id:
        messages.error(request, "You must be logged in as a staff member to access this page.")
        return redirect('login')  # or wherever you want to redirect

    staff = get_object_or_404(Staff, id=staff_id, role='DOCTOR')
    assignment = get_object_or_404(PatientAssignment, id=assignment_id, staff=staff)
    prescriptions = Prescription.objects.filter(patient_assignment=assignment)

    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.patient_assignment = assignment
            prescription.save()
            
            # Create a notification for the patient
            Notification.objects.create(
                user=assignment.patient,
                message=f"New prescription added: {prescription.medication}."
            )
            
            messages.success(request, 'Prescription added successfully.')
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
                user=appointment.patient_assignment.patient,
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
                user=appointment.patient_assignment.patient,
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
            user=appointment.patient_assignment.patient,
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
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'notification_center.html', {'notifications': notifications})

def messaging(request):
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        content = request.POST.get('content')
        recipient = get_object_or_404(User, id=recipient_id)
        
        Message.objects.create(sender=request.user, recipient=recipient, content=content)
        messages.success(request, 'Message sent successfully.')
        
        # Create a notification for the recipient
        Notification.objects.create(
            user=recipient,
            message=f"New message from {request.user.get_full_name() or request.user.username}."
        )
        
        return redirect('messaging')

    received_messages = Message.objects.filter(recipient=request.user).order_by('-timestamp')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-timestamp')
    
    context = {
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    }
    return render(request, 'messaging.html', context)

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
            user=appointment.patient_assignment.staff.user,
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
                user=appointment.patient_assignment.patient,
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