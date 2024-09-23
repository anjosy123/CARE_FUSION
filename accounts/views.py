from django.shortcuts import render,HttpResponse,redirect
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Organizations

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
        return redirect(reverse('index'))  # Redirect to index page after logout
    else:
        messages.warning(request, "You are not logged in.")  # Optional message for not logged in users
    return redirect(reverse('login'))

def handle_org_login(request):
    if request.method == "POST":
        username = request.POST.get("org_username")
        password = request.POST.get("org_password")
        org_user = authenticate(request, username=username, password=password)
        if org_user is not None:
            login(request, org_user)
            return redirect('organizations_home')  # Redirect to the organizations home page
        else:
            messages.error(request, "Invalid username or password")
            return redirect('org_login')
    return render(request, 'account/org_login.html')

def register_organization(request):
    if request.method == "POST":
        username = request.POST.get("org_username")
        email = request.POST.get("org_email")
        name = request.POST.get("org_name")
        address = request.POST.get("org_address")
        phone = request.POST.get("org_phone")
        password = request.POST.get("org_password")
        confirm_password = request.POST.get("org_confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('org_signup')

        # Create a new organization with a hashed password
        new_org = Organizations(
            org_username=username,
            org_email=email,
            org_name=name,
            org_address=address,
            org_phone=phone
        )
        new_org.set_password(password)
        new_org.save()
        messages.success(request, "Organization registered successfully!")
        return redirect('org_login')  # Redirect to login after registration

    return render(request, 'account/register.html')  # Render the registration form

from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.contrib import messages

def org_logout(request):
    if request.user.is_authenticated:
        auth_logout(request)
        messages.success(request, "You have been successfully logged out.")
    return redirect('index')  # Redirect to the home page after logout