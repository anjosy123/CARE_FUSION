from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.contrib.auth import logout, get_user_model
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib.auth.hashers import check_password
from django.views.decorators.cache import cache_control, never_cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from care_fusion import settings
from .models import Organizations,Contact,ServiceRequest
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import random, logging, os
from .forms import ServiceRequestForm   
from django.utils import timezone

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
    status_filter = request.GET.get('status')
    # Base queryset
    service_requests = ServiceRequest.objects.filter(patient_id=user_id)
    
    # Apply status filter if not 'ALL'
    if status_filter != 'ALL':
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
        cphone = request.POST.get("phone")
        desc = request.POST.get("description")
        query = Contact(fname=name,email=email,phone=cphone,description=desc)
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

def handlelogin(request):
    if request.method == "POST":
        uname = request.POST.get("email")
        pass1 = request.POST.get("pass1")
        try:
            # Fetch user by email
            myuser = User.objects.get(email=uname)
            
            # Check if the user is an admin (based on email or any other identifier)
            if myuser.email == "anjosyaj2025@mca.ajce.in":
                # Check if the provided password matches the hashed password
                if check_password(pass1, myuser.password):
                    # Set session for admin user
                    request.session['user_id'] = myuser.id
                    request.session['role'] = 'admin'
                    return redirect('admin_dashboard')
                else:
                    messages.error(request, "Invalid Admin Credentials")
                    return redirect('login')
            else:
                # Check if it's a normal user and verify their password
                if check_password(pass1, myuser.password):
                    # Set session for normal user
                    request.session['user_id'] = myuser.id
                    request.session['role'] = 'user'
                    request.session['username']=myuser.username
                    request.session['email']=myuser.email
                    # "Redirecting to patients_dashboard"

                    return redirect('patients_dashboard')
                else:
                    messages.error(request, "Invalid Credentials")
                    return redirect('login')
        except User.DoesNotExist:
            messages.error(request, "Invalid Email")
            return redirect('login')

    return render(request, 'Users/login.html')


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
# @login_required
def patients_dashboard(request):
    # Check if the user is logged in via session
    if request.session.has_key('user_id'):
        query = request.GET.get('q', '')  # Get the search query from the URL
        if query:
            organizations = Organizations.objects.filter(org_name__icontains=query, approve=1)
        else:
            organizations = Organizations.objects.filter(approve=1)  # Fetch all approved organizations if no search query is provided
            
        service_requests = ServiceRequest.objects.filter(patient_id=request.session['user_id']).order_by('-created_at')
        
        context = {
            'organizations': organizations,
            'query': query,
            'service_requests': service_requests,
        }
        return render(request, 'Users/patients_dashboard.html', context)
    else:
        return redirect('login')


def handle_org_login(request):
    if request.method == "POST":
        username = request.POST.get("org_username")
        password = request.POST.get("org_password")
        try:
            # Fetch user by org_regid
            org_user = Organizations.objects.get(org_regid=username)
            if org_user and org_user.org_password == password:
                if org_user.approve == 1:
                    # Store session data for organization login
                    request.session['org_id'] = org_user.id  # Store the database ID
                    request.session['org_regid'] = org_user.org_regid  # Store the org_regid
                    request.session['org_name'] = org_user.org_name
                    print(f"Logged in: org_id={org_user.id}, org_regid={org_user.org_regid}")  # Debug print
                    return redirect('palliatives_dashboard')
                else:
                    messages.error(request, "Organization is not approved yet!")
            else:
                messages.error(request, "Invalid password")
        except Organizations.DoesNotExist:
            messages.error(request, "Invalid username or password")
        
        return redirect('org_login')

    return render(request, 'Organizations/org_login.html')



@never_cache
def palliatives_dashboard(request):
    org_id = request.session.get('org_id')
    # org_regid = request.session.get('org_regid')
    if org_id:
        organization = Organizations.objects.get(id=org_id)
        pending_requests = ServiceRequest.objects.filter(organization=organization, status='pending').order_by('-created_at')
        context = {
            'pending_requests': pending_requests,
        }
        return render(request, 'Organizations/palliatives_dashboard.html', context)
    else:
        return redirect('org_login')


def handlesignup(request):
    if request.method == "POST":
        uname = request.POST.get("username")
        firstname = request.POST.get("fname")
        lastname = request.POST.get("lname")
        email = request.POST.get("email")
        password = request.POST.get("pass1")
        confirmpassword = request.POST.get("pass2")

        # Check if passwords match
        if password != confirmpassword:
            messages.warning(request, "Passwords do not match")
            return redirect(reverse('signup'))
        
        # Check if username already exists in the Patient model (use 'name' instead of 'username')
        try:
            if User.objects.get(username=uname):
                messages.info(request, "Username is already taken")
                return redirect(reverse('signup'))
        except User.DoesNotExist:
            pass  # Continue if the username is not found

        # Check if email already exists in the Patient model
        try:
            if User.objects.get(email=email):
                messages.info(request, "Email is already registered")
                return redirect(reverse('signup'))
        except User.DoesNotExist:
            pass  # Continue if the email is not found
        
        # Create new user and save to the database
        myuser = User.objects.create_user(username=uname, first_name=firstname, last_name=lastname, email=email, password=password)
        myuser.save()
        
        messages.success(request, "Signup successful! Please log in.")
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
        # org_username = request.POST['org_username']
        org_email = request.POST['org_email']
        org_name = request.POST['org_name']
        org_regid = request.POST['org_regid']  # New Organization Registration Number
        org_address = request.POST['org_address']
        org_phone = request.POST['org_phone']
        org_pincode = request.POST['org_pincode']  # Pincode field
        org_pass1 = request.POST['org_pass1']
        org_pass2 = request.POST['org_pass2']
        
        # Check if passwords match
        if org_pass1 != org_pass2:
            messages.error(request, "Passwords do not match!")
            return redirect('org_signup')  # Replace with the correct URL name

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
            pincode=org_pincode,  # Pincode
            org_password=org_pass1,  # Store hashed password
            approve=False  # By default, approval status is False
        )
        organization.save()  # Save to the database

        messages.success(request, "Organization registered successfully. Awaiting admin approval.")
        return redirect('org_login')  # Redirect to login or another page after signup
    
    return render(request, 'Organizations/org_signup.html')  # Render the registration form

def org_logout(request):
    request.session.delete()
    logout(request)
    return redirect('org_login')  # Redirect to the login page after logout


def providers_list(request):
    return render(request, 'Organizations/providers_list.html')

user_pins={}

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate a random 4-digit code
            code = random.randint(1000, 9999)
            user_pins[email] = code

            # Send email with the code
            send_mail(
                'Password Reset Code',
                f'Your password reset code is {code}.',
                'admin@yourdomain.com',  # Change to your domain
                [email],
                fail_silently=False,
            )
            # Redirect to the verification page
            return redirect('verify_code', email=email)
        except User.DoesNotExist:
        # except Patient.DoesNotExist:
            messages.error(request, 'Invalid email address.')
    return render(request, 'Forgot_Password/forgot_password.html')

# Verify code view
def verify_code(request, email):
    if request.method == 'POST':
        entered_code = request.POST.get('pin')
        correct_code = user_pins.get(email)

        if correct_code and str(entered_code) == str(correct_code):
            # Redirect to reset password page
            return redirect('reset_password', email=email)
        else:
            messages.error(request, 'Invalid code. Please try again.')

    return render(request, 'Forgot_Password/verifycode.html',{'email': email})

# Reset password view
def reset_password(request, email):
    if request.method == 'POST':
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if new_password1 and new_password2:
            if new_password1 == new_password2:
                User = get_user_model()
                try:
                    user = User.objects.get(email=email)
                    user.password = make_password(new_password1)  # Use new_password1 here
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

User = get_user_model()

def manage_users(request):
    users = User.objects.exclude(email="anjosyaj2025@mca.ajce.in")
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
    try:
        organization = Organizations.objects.get(org_regid=org_id)
    except Organizations.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Organization not found.'}, status=404)

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST, request.FILES)
        if form.is_valid():
            service_request = form.save(commit=False)
            
            # Get the User instance using the user_id from the session
            user_id = request.session.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    service_request.patient = user
                except User.DoesNotExist:
                    return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
            else:
                return JsonResponse({'success': False, 'message': 'User is not authenticated.'}, status=401)
            
            service_request.organization = organization
            service_request.save()

            # Send confirmation email
            send_confirmation_email(user, organization, service_request)
            messages.success(request, 'Service request submitted successfully.')
            return redirect('patients_dashboard')
            # return JsonResponse({'success': True, 'message': 'Service request submitted successfully.'})
        # else:
            # return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ServiceRequestForm()
    
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