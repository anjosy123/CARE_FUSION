from django.utils import timezone
from datetime import timedelta
from .models import MonthlyRentalPayment
from .utils import send_payment_reminder, send_rental_cancellation_notice

def check_overdue_payments():
    # Get overdue payments
    overdue_payments = MonthlyRentalPayment.objects.filter(
        payment_status='PENDING',
        month_end_date__lt=timezone.now().date() - timedelta(days=7),
        warning_sent=False
    )
    
    for payment in overdue_payments:
        # Send warning first time
        if not payment.warning_sent:
            send_payment_reminder(payment)
            payment.warning_sent = True
            payment.save()
        
        # If still not paid after 7 days of warning
        if payment.warning_sent and timezone.now().date() > payment.month_end_date + timedelta(days=14):
            rental = payment.rental
            rental.status = 'CANCELLED'
            rental.save()
            send_rental_cancellation_notice(rental) 