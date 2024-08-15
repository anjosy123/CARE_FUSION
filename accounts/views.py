from django.shortcuts import render
# from django.contrib import messages
from .forms import UserRegisterForm

# Create your views here.
def home_view(request):
    print("home view called")
    return render(request, 'index.html')
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()