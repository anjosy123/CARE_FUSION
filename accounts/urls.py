from django.urls import path, include
from django.views.generic import TemplateView
from.import views


urlpatterns = [
    path('', views.index, name='index'),
    path('regOrg/', views.regOrg, name='regOrg'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('login/', views.loginn, name='login'),
    path('signup/', views.signup, name='signup'),
    path('', TemplateView.as_view(template_name='pages/index.html'), name='home'),
    path('accounts/', include('allauth.urls')),
]