from django.urls import path, include
from django.views.generic import TemplateView
from.import views
from .views import handlesignup, organizations_home
from .views import handlelogin
from .views import handlelogout
from .views import index, about, organizations_home, handle_org_login, contact, services, handlelogin, handlesignup, handlelogout
from .views import register_organization  # Import your views
from .views import org_logout
from .views import restricted_providers, providers_list, providers_list

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
    path('organizations/', organizations_home, name='organizations_home'), 
    path('org_login/', handle_org_login, name='org_login'),  # URL for organization login
    path('org_signup/', register_organization, name='org_signup'),  # URL for organization signup
    path('org_logout/', org_logout, name='org_logout'),
    path('restricted_providers/', restricted_providers, name='restricted_providers'),
    path('providers/', views.providers_list, name='providers'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-code/<str:email>/', views.verify_code, name='verify_code'),
    path('reset-password/<str:email>/', views.reset_password, name='reset_password'),
]