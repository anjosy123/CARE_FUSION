from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.template.loader import render_to_string
from .models import Staff, PatientAssignment, ServiceRequest, FareStage, Notification, DriverLeave, MonthlyRentalPayment
from twilio.rest import Client
from django.utils import timezone
import googlemaps, razorpay
from django.core.mail import EmailMessage
from django.utils.html import strip_tags
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
import os
from datetime import datetime, timedelta
from decimal import Decimal
from calendar import monthrange

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

def send_verification_email(email, token, is_organization=False):
    try:
        subject = 'Verify your email address'
        
        # Different verification URLs for users and organizations
        if is_organization:
            verification_url = f"{settings.BASE_URL}/verify-email/{token}/true/"
        else:
            verification_url = f"{settings.BASE_URL}/verify-user-email/{token}/"
            
        message = f'Click the following link to verify your email address: {verification_url}'
        
        email_message = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email]
        )
        email_message.send()
        return True
    except Exception as e:
        print(f"Error sending verification email: {str(e)}")
        return False

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

def create_rental_payment_order(rental):
    """Create Razorpay order for equipment rental"""
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    # Calculate total amount (rental amount + security deposit)
    total_amount = float(rental.daily_rental_price + rental.deposit_amount)
    
    # Convert to paise (Razorpay expects amount in smallest currency unit)
    amount_in_paise = int(total_amount * 100)
    
    # Create order data
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'payment_capture': 1,  # Auto-capture payment
        'notes': {
            'rental_id': str(rental.id),
            'equipment_name': rental.equipment.name,
            'patient_name': rental.patient.get_full_name()
        }
    }
    
    try:
        # Create Razorpay order
        order = client.order.create(data=order_data)
        
        # Update rental with order ID
        rental.razorpay_order_id = order['id']
        rental.save()
        
        return order
    except Exception as e:
        print(f"Error creating Razorpay order: {str(e)}")
        return None

def verify_rental_payment(payment_id, order_id, signature):
    """Verify Razorpay payment signature"""
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    try:
        client.utility.verify_payment_signature({
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False

def send_rental_payment_notification(rental, payment):
    """Send notifications about successful payment to both patient and organization"""
    # Send to patient
    subject = 'Payment Confirmation - Equipment Rental'
    template = 'emails/rental_payment_patient.html'
    
    context = {
        'rental': rental,
        'payment': payment,
        'domain': settings.BASE_URL,
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[rental.patient.email],
        html_message=html_message
    )
    
    # Send to organization
    subject = 'New Rental Payment Received'
    template = 'emails/rental_payment_organization.html'
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[rental.equipment.organization.org_email],
        html_message=html_message
    )

def generate_rental_receipt(rental, payment):
    """Generate PDF receipt for rental payment"""
    filename = f"rental_receipt_{rental.id}_{payment.id}.pdf"
    filepath = os.path.join(settings.MEDIA_ROOT, 'receipts', filename)
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Add header with logo and company details
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, "CareFusion")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, "Healthcare Equipment Rentals")
    
    # Add receipt details in a box
    c.rect(40, height - 320, width - 80, 230)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 100, f"RECEIPT")
    c.setFont("Helvetica", 12)
    
    # Receipt metadata
    c.drawString(50, height - 120, f"Receipt No: {payment.id}")
    c.drawString(50, height - 140, f"Date: {payment.payment_date.strftime('%d-%m-%Y %H:%M')}")
    c.drawString(50, height - 160, f"Payment ID: {payment.razorpay_payment_id}")
    
    # Customer details
    c.drawString(50, height - 190, "Customer Details:")
    c.setFont("Helvetica", 11)
    c.drawString(70, height - 210, f"Name: {rental.patient.get_full_name()}")
    c.drawString(70, height - 230, f"Email: {rental.patient.email}")
    
    # Rental details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 260, "Rental Details:")
    c.setFont("Helvetica", 11)
    c.drawString(70, height - 280, f"Equipment: {rental.equipment.name}")
    c.drawString(70, height - 300, f"Organization: {rental.equipment.organization.org_name}")
    
    # Payment breakdown
    c.setFont("Helvetica-Bold", 12)
    y = height - 340
    c.drawString(50, y, "Payment Breakdown:")
    c.setFont("Helvetica", 11)
    
    # Table headers
    y -= 25
    c.drawString(70, y, "Description")
    c.drawString(300, y, "Amount")
    
    # Table content
    y -= 20
    c.drawString(70, y, "Daily Rental Rate")
    c.drawRightString(400, y, f"₹{rental.daily_rental_price}")
    
    y -= 20
    c.drawString(70, y, "Rental Period")
    c.drawString(300, y, "30 days")
    
    y -= 20
    c.drawString(70, y, "Security Deposit")
    c.drawRightString(400, y, f"₹{rental.deposit_amount}")
    
    # Total
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(70, y, "Total Amount")
    c.drawRightString(400, y, f"₹{payment.amount}")
    
    # Footer
    c.setFont("Helvetica", 9)
    c.drawString(50, 50, "This is a computer generated receipt and does not require signature.")
    c.drawString(50, 35, f"Generated on: {timezone.now().strftime('%d-%m-%Y %H:%M:%S')}")
    
    c.save()
    return os.path.join(settings.MEDIA_URL, 'receipts', filename)

def send_rental_request_notification(rental):
    """Send notification to organization about new rental request"""
    subject = "New Equipment Rental Request"
    template = 'emails/rental_request_organization.html'
    
    context = {
        'rental': rental,
        'domain': settings.BASE_URL,
        'STATIC_URL': settings.STATIC_URL  # Add STATIC_URL to context
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[rental.equipment.organization.org_email],
            html_message=html_message
        )
        return True
    except Exception as e:
        print(f"Error sending rental request notification: {str(e)}")
        return False

def send_rental_approval_notification(rental):
    """Send notification to patient about rental approval"""
    subject = 'Your Rental Request has been Approved'
    template = 'emails/rental_approval_patient.html'
    
    context = {
        'rental': rental,
        'domain': settings.BASE_URL,
        'static': settings.STATIC_URL,  # Add this for static files in email
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[rental.patient.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"Error sending rental approval notification: {str(e)}")
        return False

def send_rental_rejection_notification(rental):
    """Send notification to patient about rental rejection"""
    subject = 'Your Rental Request has been Declined'
    template = 'emails/rental_rejection_patient.html'
    
    context = {
        'rental': rental,
        'domain': settings.BASE_URL,
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[rental.patient.email],
        html_message=html_message
    )

def send_delivery_otp(delivery):
    """Send OTP to patient via SMS and email"""
    patient = delivery.rental.patient
    otp = delivery.delivery_otp
    
    # Send SMS
    message = f"Your CareFusion delivery OTP is {otp}. Share this with the volunteer to complete the delivery."
    send_sms(patient.phone_number, message)
    
    # Send email
    subject = "CareFusion Delivery OTP"
    template = 'emails/delivery_otp.html'
    context = {
        'patient': patient,
        'delivery': delivery,
        'otp': otp
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[patient.email],
        html_message=html_message
    )

def calculate_monthly_rent(rental):
    """Calculate the monthly rent amount including any late fees"""
    # Get days in current month
    today = timezone.now().date()
    _, days_in_month = monthrange(today.year, today.month)
    
    # Calculate base rent
    daily_rate = rental.daily_rental_price
    base_amount = daily_rate * days_in_month
    
    # Check for any late fees from previous month
    previous_payment = MonthlyRentalPayment.objects.filter(
        rental=rental,
        month_end_date__lt=today,
        payment_status='OVERDUE'
    ).first()
    
    late_fee = 0
    if previous_payment:
        # Add 10% late fee
        late_fee = previous_payment.amount_due * Decimal('0.10')
    
    return base_amount + late_fee

def create_monthly_rental_order(payment):
    """Create Razorpay order for monthly rental payment"""
    try:
        amount = int(payment.amount_due * 100)  # Convert to paise
        
        # Create Razorpay order
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'rental_id': str(payment.rental.id),
                'payment_id': str(payment.id),
                'payment_type': 'MONTHLY_RENT'
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        # Update payment with order ID
        payment.razorpay_order_id = order['id']
        payment.save()
        
        return order
        
    except Exception as e:
        print(f"Error creating Razorpay order: {str(e)}")
        raise

def send_payment_reminder(payment):
    """Send payment reminder email and SMS to patient"""
    subject = 'Rental Payment Reminder'
    template = 'emails/payment_reminder.html'
    context = {
        'payment': payment,
        'rental': payment.rental,
        'due_date': payment.month_end_date,
        'amount': payment.amount_due
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[payment.rental.patient.email],
        html_message=html_message
    )
    
    # Send SMS
    message = f"Payment Reminder: Your monthly rental payment of ₹{payment.amount_due} is due by {payment.month_end_date}. Please pay to avoid late fees."
    send_sms(payment.rental.patient.phone_number, message)

def send_rental_cancellation_notice(rental):
    """Send rental cancellation notice to patient"""
    subject = 'Rental Service Cancelled'
    template = 'emails/rental_cancellation.html'
    context = {
        'rental': rental,
        'cancellation_date': timezone.now().date()
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[rental.patient.email],
        html_message=html_message
    )
    
    # Send SMS
    message = f"Your rental service for {rental.equipment.name} has been cancelled due to payment default. Please contact support for assistance."
    send_sms(rental.patient.phone_number, message)

def create_refund_order(rental, amount):
    """Create Razorpay refund order for deposit"""
    try:
        refund_data = {
            'amount': int(amount * 100),  # Convert to paise
            'speed': 'NORMAL',  # or 'INSTANT'
            'notes': {
                'rental_id': str(rental.id),
                'refund_type': 'DEPOSIT_REFUND'
            }
        }
        
        refund = razorpay_client.payment.refund(rental.razorpay_payment_id, refund_data)
        return refund
        
    except Exception as e:
        print(f"Error creating refund order: {str(e)}")
        raise

def send_rental_end_notification(rental):
    """Send email notification about rental end and deposit refund"""
    subject = 'Rental Service Ended - Deposit Refund Initiated'
    template = 'emails/rental_end_notification.html'
    
    context = {
        'rental': rental,
        'equipment': rental.equipment,
        'deposit_amount': rental.deposit_amount,
        'return_deadline': timezone.now() + timedelta(hours=24)
    }
    
    html_message = render_to_string(template, context)
    plain_message = strip_tags(html_message)
    
    # Send email to patient
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[rental.patient.email],
        html_message=html_message
    )
    
    # Send SMS notification
    message = (
        f"Your rental for {rental.equipment.name} has been ended. "
        f"Please return the equipment within 24 hours. "
        f"Deposit refund of ₹{rental.deposit_amount} will be processed after inspection."
    )
    send_sms(rental.patient.phone_number, message)