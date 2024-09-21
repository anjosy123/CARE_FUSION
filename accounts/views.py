from django.shortcuts import render,HttpResponse,redirect
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User  # Keep this import
from django.urls import reverse  # Import reverse for URL resolution
from .models import Organization  # Correctly import Organization from your models

# Create your views here.
def home_view(request):
    return render(request, 'pages/index.html')

def index(request):
    return render(request, 'pages/index.html')

def about(request):
    return render(request, 'pages/about.html')

def contact(request):
    return render(request, 'pages/contact.html')

def services(request):
    return render(request, 'pages/services.html')

def handlelogin(request):
    if request.method == "POST":
        uname = request.POST.get("username")
        pass1 = request.POST.get("pass1")
        myuser = authenticate(username = uname,password = pass1)
        if myuser is not None:
            login(request,myuser)
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
            if User.objects.get(username=uname):
                messages.info(request,"UserName Is Taken")
                return redirect(reverse('signup'))
        except:
            pass
        
        try:
            if User.objects.get(email=email):
                messages.info(request,"Email Is Taken")
                return redirect(reverse('signup'))
        except:
            pass
        
        # print(uname,email,password,confirmpassword)
        myuser=User.objects.create_user(uname,email,password)
        myuser.save()
        messages.success(request,"Signup Success Please Login!")
        return redirect(reverse('login'))
    
    return render(request, 'account/signup.html')

def handlelogout(request):
    if request.user.is_authenticated:  # Check if the user is logged in
        logout(request)
        messages.info(request, "Logout Success")
    else:
        messages.warning(request, "You are not logged in.")  # Optional message for not logged in users
    return redirect(reverse('login'))

def organizations_home(request):
    return render(request, 'pages/organizations.html')

def handle_org_login(request):
    if request.method == "POST":
        org_username = request.POST.get("org_username")
        org_password = request.POST.get("org_pass1")
        
        # Authenticate the user
        org_user = authenticate(username=org_username, password=org_password)
        
        if org_user is not None:
            login(request, org_user)
            messages.success(request, "Organization Login Success")
            return redirect('organizations_home')  # Redirect to the organizations home page
        else:
            messages.error(request, "Invalid Credentials")
            return redirect(reverse('org_login'))  # Redirect back to the login page

    return render(request, 'account/org_login.html')

def handle_org_signup(request):
    if request.method == 'POST':
        orgusername = request.POST['org_username']
        orgemail = request.POST['org_email']
        orgpassword = request.POST['org_pass1']
        orgconfpassword = request.POST['org_pass2']
        orgname = request.POST.get('org_name')  # Assuming you add this field in the form
        orgaddress = request.POST.get('org_address')  # Assuming you add this field in the form
        orgphone = request.POST.get('org_phone')  # Assuming you add this field in the form

        # Check if passwords match
        if orgpassword != orgconfpassword:
            messages.error(request, "Passwords do not match.")
            return render(request, 'account/org_signup.html')

        # Check if the username already exists
        if User.objects.filter(username=orgusername).exists():  # Change to filter by username
            messages.error(request, "Username already exists. Please choose a different one.")
            return render(request, 'account/org_signup.html')

        try:
            # Create user
            user = User.objects.create_user(username=orgusername, email=orgemail, password=orgpassword)
            user.save()

            # Create organization
            organization = Organization.objects.create(
                name=orgname,
                email=orgemail,
                address=orgaddress,
                phone_number=orgphone,
                user=user  # This should work correctly now
            )
            organization.save()

            messages.success(request, "User and organization created successfully.")
            return redirect('login')
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'account/org_signup.html')

    return render(request, 'account/org_signup.html')

def handle_org_logout(request):
    return render(request, 'account/org_logout.html')