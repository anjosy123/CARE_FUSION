from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from .models import Staff, PatientAssignment, ServiceRequest

def send_verification_email(email, token, is_organization=False):
    subject = 'Verify your email address'
    verification_link = reverse('verify_email', kwargs={'token': token, 'is_organization': int(is_organization)})
    message = f'Please click the following link to verify your email address: {settings.BASE_URL}{verification_link}'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]
    send_mail(subject, message, from_email, recipient_list)

def get_dashboard_context(organization):
    staff_count = Staff.objects.filter(organization=organization, is_active=True).count()
    
    assigned_patients = PatientAssignment.objects.filter(organization=organization, is_active=True)
    assigned_patients_count = assigned_patients.count()
    
    pending_requests = ServiceRequest.objects.filter(organization=organization, status='PENDING')
    approved_requests = ServiceRequest.objects.filter(organization=organization, status='APPROVED')
    rejected_requests = ServiceRequest.objects.filter(organization=organization, status='REJECTED')
    
    recent_assignments = PatientAssignment.objects.filter(
        organization=organization,
        is_active=True
    ).select_related('patient', 'staff').order_by('-assigned_date')[:5]

    return {
        'organization': organization,
        'staff_count': staff_count,
        'assigned_patients_count': assigned_patients_count,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
        'recent_assignments': recent_assignments,
    }
