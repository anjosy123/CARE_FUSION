from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib import messages
from .forms import UserRegisterForm

# Create your views here.
@login_required
def home_view(request):
    return render(request, 'index.html')
def account_page(request):
    return render(request, 'accounts/account_page.html')
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()