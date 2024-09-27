from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session  # Import Session
from django.contrib.auth import login  # Import login for session authentication
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Organizations,Patient,Contact
from django.contrib.auth import get_user_model
import random
from django.core.mail import send_mail
# Create your views here.
def home_view(request):
    return render(request, 'index.html')

def index(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

def organizations_home(request):
        return render(request, 'Organizations/organizations_home.html')

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

def admin_dashboard(request):
    return render(request, 'Admin/admin.html')

def handlelogin(request):
    if request.method == "POST":
        uname = request.POST.get("email")
        pass1 = request.POST.get("pass1")
        try:
            myuser = Patient.objects.get(email=uname)
            if myuser.email == "admin@gmail.com" and myuser.password == "Admin@123":
                # Set session for admin user
                request.session['user_id'] = myuser.id  # Save user ID in session
                request.session['role'] = 'admin'       # Store user role in session
                return redirect('admin_dashboard')
            else:
                if myuser.password == pass1:
                    # Set session for normal user
                    request.session['user_id'] = myuser.id
                    request.session['role'] = 'user'
                    messages.success(request, "Login Success")
                    return redirect('patients_dashboard')  # Redirect after successful login
                else:
                    messages.error(request, "Invalid Credentials")
                    return redirect('login')
        except Patient.DoesNotExist:
            messages.error(request, "Invalid Email")
            return redirect('login')
        
    return render(request, 'Users/login.html')

def handlesignup(request):
    if request.method == "POST":
        uname = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("pass1")
        confirmpassword = request.POST.get("pass2")
        if password != confirmpassword:
            messages.warning(request,"Password is Incorrect")
            return redirect(reverse('signup'))
        
        try:
            if Patient.objects.get(username=uname):
                messages.info(request,"UserName Is Taken")
                return redirect(reverse('signup'))
        except:
            pass
        
        try:
            if Patient.objects.get(email=email):
                messages.info(request,"Email Is Taken")
                return redirect(reverse('signup'))
        except:
            pass
        
        # print(uname,email,password,confirmpassword)
        myuser=Patient(name=uname,email=email,password=password,role="User")
        myuser.save()
        messages.success(request,"Signup Success Please Login!")
        return redirect(reverse('login'))
    
    return render(request, 'Users/signup.html')

def handlelogout(request):
    if request.user.is_authenticated or request.session.get('user_id') or request.session.get('org_id'):
        logout(request)
        request.session.flush()  # Clear session data
        messages.info(request, "Logout Success")
    else:
        messages.warning(request, "You are not logged in.")
    return redirect('index')

def handle_org_login(request):
    if request.method == "POST":
        username = request.POST.get("org_username")
        password = request.POST.get("org_password")
        try:
            org_user = Organizations.objects.get(org_regid=username)
            if org_user and org_user.org_password == password:
                if org_user.approve == 1:
                    # Store session data for organization login
                    request.session['org_id'] = org_user.id
                    request.session['role'] = 'organization'
                    return redirect('palliatives_dashboard')  # Redirect to the palliatives dashboard
                else:
                    messages.error(request, "Organization is not approved yet!")
                    return redirect('org_login')
            else:
                messages.error(request, "Invalid password")
                return redirect('org_login')
        except Organizations.DoesNotExist:
            messages.error(request, "Invalid username or password")
            return redirect('org_login')

    return render(request, 'Organizations/org_login.html')

def register_organization(request):
    if request.method == 'POST':
        org_username = request.POST['org_username']
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

from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.contrib import messages

def org_logout(request):
    if request.user.is_authenticated:
        auth_logout(request)
        messages.success(request, "You have been successfully logged out.")
    return redirect('index')  # Redirect to the home page after logout

from django.shortcuts import render, redirect
from django.contrib import messages

def restricted_providers(request):
    if not request.user.is_authenticated:
        messages.warning(request, "Only registered users can use this functionality.")
        return redirect('login')
    return redirect('Organizations/providers_list.html')

def providers_list(request):
    return render(request, 'Organizations/providers_list.html')

user_pins={}

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = Patient.objects.get(email=email)
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
        except Patient.DoesNotExist:
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

    return render(request, 'verifycode.html',{'email': email})

# Reset password view
def reset_password(request, email):
    if request.method == 'POST':
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if new_password1 == new_password2:
            try:
                user = Patient.objects.get(email=email)
                user.password = new_password1  # Directly set the password
                user.save()  # Save the changes to the database
                messages.success(request, 'Password has been reset successfully.')
                return redirect('login')
            except Patient.DoesNotExist:
                messages.error(request, 'Invalid user.')
        else:
            messages.error(request, 'Passwords do not match.')

    return render(request, 'Forgot_Password/resetpassword.html',{'email':email})

User = get_user_model()

def manage_users(request):
    users = Patient.objects.exclude(email="admin@gmail.com")
    return render(request, 'Admin/manage_users.html', {'users': users})

def edit_user(request, user_id):
    user = get_object_or_404(Patient, id=user_id)
    
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
    user = get_object_or_404(Patient, id=user_id)
    
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


@login_required
def patients_dashboard(request):
    query = request.GET.get('q', '')  # Get the search query from the URL
    if query:
        organizations = Organizations.objects.filter(org_name__icontains=query, approve=1)  # Use 'approve=1' instead of 'is_approved'
    else:
        organizations = Organizations.objects.filter(approve=1)  # Fetch all approved organizations if no search query is provided

    # Render the template with the organizations
    return render(request, 'Users/patients_dashboard.html', {
        'organizations': organizations,
        'query': query,
    })



def palliatives_dashboard(request):
    return render(request, 'Organizations/palliatives_dashboard.html')