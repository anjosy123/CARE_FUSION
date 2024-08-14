from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserRegisterForm
from django.contrib.auth.views import LoginView, LogoutView

# Create your views here.

class CustomLoginView(LoginView):
    template_name = 'login.html'
    
class CustomLogoutView(LogoutView):
    template_name = 'logout.html'
def home(request):
    return render(request, 'index.html')
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
        else:
            form = UserRegisterForm()
        return render(request, 'register.html',{'form':form})
    