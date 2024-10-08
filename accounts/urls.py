from django.urls import path, include
from django.views.generic import TemplateView
from . import views
from .views import (
    index, about, organizations_home, contact, services, handlelogin, 
    handlesignup, handlelogout, register_organization, org_logout, handle_service_request
)

urlpatterns = [
    path('', index, name='index'),  # Homepage pointing to index view
    path('accounts', include('allauth.urls')),  # For Google and other social logins
    path('contact', contact, name='contact'),
    path('about', about, name='about'),
    path('services', services, name='services'),
    path('handle-service-request/', handle_service_request, name='handle_service_request'),
    path('submit-service-request/<str:org_id>/', views.submit_service_request, name='submit_service_request'),
    # User login, signup, and logout
    path('login', handlelogin, name='login'),
    path('signup', handlesignup, name='signup'),
    path('logout', handlelogout, name='logout'),
    path('user_notification_dashboard', views.user_notification_dashboard, name='user_notification_dashboard'),
    # Organization login, signup, and logout
    path('organizations_home', organizations_home, name='organizations_home'), 
    path('org_login', views.handle_org_login, name='org_login'),  # Organization login
    path('org_signup', register_organization, name='org_signup'),  # Organization signup
    path('org_logout', org_logout, name='org_logout'),
    
    # Provider routes
    path('providers', views.providers_list, name='providers'),
    
    # Password reset and management
    path('forgot-password', views.forgot_password, name='forgot_password'),
    path('verify-code/<str:email>', views.verify_code, name='verify_code'),
    path('reset-password/<str:email>', views.reset_password, name='reset_password'),
    
    # Admin dashboard and user management
    path('admin_dashboard', views.admin_dashboard, name='admin_dashboard'),
    path('manage-users', views.manage_users, name='manage_users'),
    path('edit-user/<int:user_id>', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>', views.delete_user, name='delete_user'),
    
    # Approve organizations
    path('approve-organizations', views.approve_organizations, name='approve_organizations'),
    path('approve-organization/<int:org_id>', views.approve_organization, name='approve_organization'),
    
    # User and organization dashboards
    path('patients_dashboard/', views.patients_dashboard, name='patients_dashboard'),
    path('palliatives_dashboard', views.palliatives_dashboard, name='palliatives_dashboard'),

    # Organizations Details
    path('organizations/<int:id>/', views.organization_detail, name='organization_detail'),
    
    # Get service requests
    path('api/service-requests/<int:request_id>/', views.get_service_request_detail, name='service_request_detail'),
    path('service-request/<int:request_id>/', views.service_request_detail, name='service_request_detail'),
    path('patient_details/<int:request_id>/', views.patient_details, name='patient_details'),
    path('service-requests/', views.service_requests, name='service_requests'),
    path('edit-service-request/<int:request_id>/', views.edit_service_request, name='edit_service_request'),
    path('delete-service-request/<int:request_id>/', views.delete_service_request, name='delete_service_request'),

]
