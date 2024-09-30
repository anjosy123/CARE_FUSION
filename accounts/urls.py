from django.urls import path, include
from django.views.generic import TemplateView
<<<<<<< HEAD
from . import views
from .views import (
    index, about, organizations_home, contact, services, handlelogin, 
    handlesignup, handlelogout, register_organization, org_logout, 
    restricted_providers,
)

urlpatterns = [
    path('', index, name='index'),  # Homepage pointing to index view
    path('accounts', include('allauth.urls')),  # For Google and other social logins
    path('contact', contact, name='contact'),
    path('about', about, name='about'),
    path('services', services, name='services'),
    
    # User login, signup, and logout
    path('login', handlelogin, name='login'),
    path('signup', handlesignup, name='signup'),
    path('logout', handlelogout, name='logout'),
    
    # Organization login, signup, and logout
    path('organizations_home', organizations_home, name='organizations_home'), 
    path('org_login', views.handle_org_login, name='org_login'),  # Organization login
    path('org_signup', register_organization, name='org_signup'),  # Organization signup
    path('org_logout', org_logout, name='org_logout'),
    
    # Provider routes
    path('restricted_providers', restricted_providers, name='restricted_providers'),
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
]
=======
from.import views
from .views import index, about, organizations_home, contact, services, handlelogin, handlesignup, handlelogout
from .views import register_organization  # Import your views
from .views import org_logout
from .views import restricted_providers

urlpatterns = [
    path('', index, name='index'),
    path('contact/', contact, name='contact'),
    path('about/', about, name='about'),
    path('index/',index, name='index'),
    path('services/', services, name='services'),
    path('', TemplateView.as_view(template_name='pages/index.html'), name='home'),
    path('accounts/', include('allauth.urls')),
    path('login', handlelogin,name='login'),
    path('signup', handlesignup,name='signup'),
    path('logout', handlelogout,name='logout'),
    path('organizations_home', organizations_home, name='organizations_home'), 
    path('org_login/', views.handle_org_login, name='org_login'),  # URL for organization login
    path('org_signup/', register_organization, name='org_signup'),  # URL for organization signup
    path('org_logout/', org_logout, name='org_logout'),
    path('restricted_providers/', restricted_providers, name='restricted_providers'),
    path('providers/', views.providers_list, name='providers'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-code/<str:email>/', views.verify_code, name='verify_code'),
    path('reset-password/<str:email>/', views.reset_password, name='reset_password'),
    path('admin_dashboard/',views.admin_dashboard, name='admin_dashboard'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('approve-organizations/', views.approve_organizations, name='approve_organizations'),
    path('approve-organization/<int:org_id>/', views.approve_organization, name='approve_organization'),
    path('patients_dashboard/',views.patients_dashboard, name='patients_dashboard'),
    path('palliatives_dashboard',views.palliatives_dashboard, name='palliatives_dashboard'),
]
>>>>>>> c836822a135e3af93d885c499392c758f76484f1
