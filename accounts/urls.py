from django.urls import path, include
from django.views.generic import TemplateView
from.import views
from .views import handlesignup


urlpatterns = [
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('index/',views.index, name='index'),
    path('organizations/', views.organizations, name='organizations'),
    path('services/', views.services, name='services'),
    path('', TemplateView.as_view(template_name='pages/index.html'), name='home'),
    path('accounts/', include('allauth.urls')),
    path('login/', views.handlelogin, name='handlelogin'),
    path('signup/', handlesignup, name='signup'),
    path('signup', handlesignup),
    path('logout/', views.handlelogout, name='handlelogout'),
]