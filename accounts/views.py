from django.shortcuts import render,HttpResponse,redirect,get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Organizations,Patient
from django.contrib.auth import get_user_model
import random
from django.core.mail import send_mail
# Create your views here.
def home_view(request):
    return render(request, 'pages/index.html')

def index(request):
    return render(request, 'pages/index.html')

def about(request):
    return render(request, 'pages/about.html')

def organizations_home(request):
    # Your logic here
        return render(request, 'pages/organizations_home.html')

def contact(request):
    return render(request, 'pages/contact.html')

def services(request):
    return render(request, 'pages/org_service_page.html')

def admin_dashboard(request):
    return render(request, 'admin.html')

def handlelogin(request):
    if request.method == "POST":
        uname = request.POST.get("email")
        pass1 = request.POST.get("pass1")
        myuser = Patient.objects.get(email=uname)
        if myuser.email =="admin@gmail.com" and myuser.password=="Admin@123":
            return redirect('admin_dashboard')
        else:
            if myuser.password == pass1:
                messages.success(request, "Login Success")
                return redirect('/')
            else:
                messages.success(request, "Invalid Credentials")
                return redirect(reverse('login'))
        
    return render(request, 'account/login.html')

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
    
    return render(request, 'account/signup.html')

def handlelogout(request):
    if request.user.is_authenticated:  # Check if the user is logged in
        logout(request)
        messages.info(request, "Logout Success")
        return redirect(reverse('index'))  # Redirect to index page after logout
    else:
        messages.warning(request, "You are not logged in.")  # Optional message for not logged in users
    return redirect(reverse('login'))

def handle_org_login(request):
    if request.method == "POST":
        username = request.POST.get("org_username")
        password = request.POST.get("org_password")
        org_user = Organizations.objects.get(org_regid=username)
        if org_user:
            if org_user.org_password == password:
                if org_user.approve==1:
                    return redirect('/')  # Redirect to the organizations home page'
                else:
                    messages.error(request, "Organization is not approved yet!")
                    return redirect('org_login')
            else:
                messages.error(request, "Invalid password")
                return redirect('org_login')
            # Redirect to the organizations home page
        else:
            messages.error(request, "Invalid username or password")
            return redirect('org_login')
    return render(request, 'account/org_login.html')

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
    
    return render(request, 'account/org_signup.html')  # Render the registration form

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
    return redirect('pages/providers_list.html')

def providers_list(request):
    return render(request, 'pages/providers_list.html')

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
    return render(request, 'forgot_password.html')

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

    return render(request, 'resetpassword.html',{'email':email})

User = get_user_model()

def manage_users(request):
    users = Patient.objects.exclude(email="admin@gmail.com")
    return render(request, 'manage_users.html', {'users': users})

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

    return render(request, 'edit_user.html', {'user': user})

def delete_user(request, user_id):
    user = get_object_or_404(Patient, id=user_id)
    
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully!')
        return redirect('manage_users')

    return render(request, 'delete_user.html', {'user': user})

def approve_organizations(request):
    unapproved_orgs = Organizations.objects.filter(approve=False)
    return render(request, 'approve_org.html', {'unapproved_orgs': unapproved_orgs})

# View for approving an organization
def approve_organization(request, org_id):
    if request.method == 'POST':
            org = Organizations.objects.get(id=org_id)
            if org:
                org.approve = True
                org.save()
    return redirect('approve_organizations')
