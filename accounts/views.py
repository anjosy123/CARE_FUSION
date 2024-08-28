from django.shortcuts import render
# from django.contrib import messages
from .forms import UserRegisterForm

# Create your views here.
def home_view(request):
    return render(request, 'pages/index.html')

def about(request):
    return render(request, 'pages/about.html')

def regOrg(request):
    return render(request, 'pages/regOrg.html')

def contact(request):
    return render(request, 'pages/contact.html')

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()