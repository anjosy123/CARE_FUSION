"""
URL configuration for care_fusion project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from accounts import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='pages/index.html'), name='home'),
    path('accounts/', include('accounts.urls')),  # Include accounts URLs
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('services/', views.services, name='services'),
    path('index/', views.index, name='index'),
    path('logout/', views.handlelogout, name='logout'),
    path('accounts/', include('allauth.urls')),
    path('organizations/', views.organizations_home, name='organizations'),  # Ensure this line is present
    path('login/', views.handlelogin, name='login'),
    path('signup/', views.handlesignup, name='signup'),
    path('org_login/', views.handle_org_login, name='org_login'),
    path('org_signup/', views.register_organization, name='org_signup'),  # Add the org_signup path
]
