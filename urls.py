from django.urls import path
from . import views

urlpatterns = [
    # ... your existing urls ...
    path('get-services/<int:org_id>/', views.get_services, name='get_services'),
] 