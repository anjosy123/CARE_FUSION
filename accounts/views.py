from django.shortcuts import render,HttpResponse,redirect
from django.contrib import messages
# from .forms import UserRegisterForm
from django.contrib.auth.models import User
from django.urls import reverse

# Create your views here.
def home_view(request):
    return render(request, 'pages/index.html')

def index(request):
    return render(request, 'pages/index.html')

def about(request):
    return render(request, 'pages/about.html')

def organizations(request):
    return render(request, 'pages/organizations.html')

def contact(request):
    return render(request, 'pages/contact.html')

def services(request):
    return render(request, 'pages/services.html')

def handlelogin(request):
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
                return HttpResponse("USERNAME IS TAKEN")
        except:
            pass
        
        try:
            if User.objects.get(email=email):
                return HttpResponse("EMAIL IS TAKEN")
        except:
            pass
        
        # print(uname,email,password,confirmpassword)
        myuser=User.objects.create_user(uname,email,password)
        myuser.save()
        return HttpResponse("Signup Succesful")
    return render(request, 'account/signup.html')

def handlelogout(request):
    return render(request, 'account/logout.html')

# def register(request):
#     if request.method == 'POST':
#         form = UserRegisterForm(request.POST)
#         if form.is_valid():
#             form.save()