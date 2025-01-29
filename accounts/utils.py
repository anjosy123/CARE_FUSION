from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.template.loader import render_to_string
from .models import Staff, PatientAssignment, ServiceRequest, FareStage, Notification, DriverLeave
from twilio.rest import Client
from django.utils import timezone
import googlemaps, razorpay

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

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
    
    
    

def send_appointment_email(appointment, action, recipient='patient'):
    if recipient == 'patient':
        to_email = appointment.patient_assignment.patient.email
        name = appointment.patient_assignment.patient.get_full_name()
    else:
        to_email = appointment.patient_assignment.staff.email
        name = appointment.patient_assignment.staff.get_full_name()

    subject = f'Appointment {action.capitalize()}'
    template = f'emails/appointment_{action}.html'
    context = {
        'name': name,
        'date_time': appointment.date_time,
        'purpose': appointment.purpose,
        'reason': appointment.cancellation_reason if action == 'cancelled' else None,
    }
    html_message = render_to_string(template, context)
    send_mail(
        subject,
        '',
        'from@example.com',
        [to_email],
        html_message=html_message,
        fail_silently=False,
    )

def calculate_distance(pickup_lat, pickup_lng, drop_lat, drop_lng):
    """Calculate distance between two points using Google Maps Distance Matrix API"""
    gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
    
    result = gmaps.distance_matrix(
        origins=f"{pickup_lat},{pickup_lng}",
        destinations=f"{drop_lat},{drop_lng}",
        mode="driving"
    )
    
    if result['status'] == 'OK':
        distance = result['rows'][0]['elements'][0]['distance']['value']
        return round(distance / 1000, 2)  # Convert meters to kilometers
    return None

def calculate_fare(organization, distance):
    """Calculate fare based on organization's fare stages"""
    fare_stages = FareStage.objects.filter(
        organization=organization,
        start_km__lte=distance
    ).order_by('-start_km').first()
    
    if fare_stages:
        base_fare = fare_stages.base_fare
        per_km_rate = fare_stages.per_km_rate
        return base_fare + (distance * per_km_rate)
    return None

def notify_about_complaint(complaint):
    """Send notifications about new complaints"""
    # Email to organization
    send_mail(
        subject=f"New Complaint - Booking #{complaint.booking.id}",
        message=f"A new complaint has been filed for booking #{complaint.booking.id}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[complaint.booking.organization.org_email]
    )
    
    # SMS to driver
    send_sms(
        phone_number=complaint.booking.driver.phone_number,
        message=f"A complaint has been filed for booking #{complaint.booking.id}"
    )

def send_sms(phone_number, message):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=phone_number
    )
    
def notify_organization_about_leave(leave):
    """Send notification to organization about new leave request"""
    organization = leave.driver.organization
    
    # Create notification
    Notification.objects.create(
        organization=organization,
        title='New Leave Request',
        message=f'Driver {leave.driver.user.get_full_name()} has requested leave from '
                f'{leave.start_date} to {leave.end_date}',
        notification_type='LEAVE_REQUEST',
        reference_id=leave.id
    )
    
    # Send email
    send_mail(
        subject='New Driver Leave Request',
        message=f'Driver {leave.driver.user.get_full_name()} has requested leave.\n\n'
                f'Type: {leave.get_leave_type_display()}\n'
                f'From: {leave.start_date}\n'
                f'To: {leave.end_date}\n'
                f'Reason: {leave.reason}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[organization.org_email]
    )
    
def notify_driver_about_leave_response(leave):
    """Send notification to driver about leave request response"""
    # Create notification
    Notification.objects.create(
        user=leave.driver.user,
        title='Leave Request Update',
        message=f'Your leave request from {leave.start_date} to {leave.end_date} has been {leave.status.lower()}.',
        notification_type='LEAVE_RESPONSE',
        reference_id=leave.id
    )
    
    # Send email
    subject = f'Leave Request {leave.status.title()}'
    message = f"""Dear {leave.driver.user.get_full_name()},

Your leave request has been {leave.status.lower()}.

Details:
- Period: {leave.start_date} to {leave.end_date}
- Type: {leave.get_leave_type_display()}
- Response Note: {leave.response_note}

"""
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[leave.driver.user.email]
    )
    
    # Send SMS
    if leave.driver.user.phone_number:
        message = f"Your leave request ({leave.start_date} to {leave.end_date}) has been {leave.status.lower()}."
        send_sms(
            phone_number=leave.driver.user.phone_number,
            message=message
        )

def get_driver_leave_status(driver, date=None):
    """Check if driver is on leave for a specific date"""
    if date is None:
        date = timezone.now().date()
    
    return DriverLeave.objects.filter(
        driver=driver,
        status='APPROVED',
        start_date__lte=date,
        end_date__gte=date
    ).exists()

def can_driver_take_bookings(driver):
    """Check if driver can take new bookings"""
    return (
        driver.is_active and 
        driver.is_available and 
        not get_driver_leave_status(driver)
    )

def create_razorpay_order(amount):
    return razorpay_client.order.create({
        'amount': int(amount * 100),  # Convert to paise
        'currency': 'INR',
        'payment_capture': '1'
    })
    
def create_razorpay_account(driver):
    return razorpay_client.contact.create({
        'name': driver.user.get_full_name(),
        'email': driver.user.email,
        'contact': driver.user.phone_number,
        'type': 'driver'
    })

def verify_razorpay_signature(order_id, payment_id, signature):
    return razorpay_client.utility.verify_payment_signature({
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    })
    
def transfer_to_driver(booking):
    return razorpay_client.transfer.create({
        'account': booking.driver.razorpay_account_id,
        'amount': int(booking.driver_earnings * 100),  # Convert to paise
        'currency': 'INR'
    })
    
def notify_payment_success(booking):
    # Notify driver
    Notification.objects.create(
        user=booking.driver.user,
        title='Payment Received',
        message=f'Payment received for booking #{booking.id}'
    )