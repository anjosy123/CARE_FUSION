from django.shortcuts import render
# from django.contrib import messages
from .forms import UserRegisterForm

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
    return render(request, 'account/signup.html')

def handlelogout(request):
    return render(request, 'account/logout.html')

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()