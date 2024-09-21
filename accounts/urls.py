from django.urls import path, include
from django.views.generic import TemplateView
from.import views
from .views import handle_org_logout, handle_org_signup, handle_org_login,organizations_home, handlelogin, handlesignup, handlelogout

urlpatterns = [
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('index/',views.index, name='index'),
    path('services/', views.services, name='services'),
    path('', TemplateView.as_view(template_name='pages/index.html'), name='home'),
    path('accounts/', include('allauth.urls')),
    path('login', handlelogin),
    path('signup', handlesignup),
    path('logout', handlelogout),
    path('organizations', views.organizations_home, name='organizations'),
    path('org_login', handle_org_login),
    path('org_signup', handle_org_signup, name='org_signup'),
    path('org_logout', handle_org_logout),
    path('org_signup/', handle_org_signup, name='org_signup'),
    path('org_login/', handle_org_login, name='org_login'),
]