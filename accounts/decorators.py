from django.shortcuts import redirect
from django.contrib import messages
from django.utils.decorators import wraps
from django.contrib.auth.models import User
from functools import wraps
from .models import TeamDashboard

def staff_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'staff_id' not in request.session:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')  # Redirect to your login page
        return view_func(request, *args, **kwargs)
    return wrapper

def organization_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'org_id' not in request.session or request.session.get('role') != 'organization':
            messages.error(request, "Please log in as an organization to access this page.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def patient_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is logged in
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        # Check if the logged-in user is a patient (not staff or organization)
        if 'org_id' in request.session or 'staff_id' in request.session:
            messages.error(request, "This page is only accessible to patients.")
            return redirect('login')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def team_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if staff is logged in
        if not request.session.get('staff_id'):
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        try:
            # Verify staff is part of a team
            team_membership = TeamDashboard.objects.select_related('team').get(
                staff_id=request.session['staff_id']
            )
            
            # Add team info to request for use in view
            request.team_membership = team_membership
            return view_func(request, *args, **kwargs)
            
        except TeamDashboard.DoesNotExist:
            messages.error(request, "You are not authorized to access this page. Team membership required.")
            return redirect('login')
            
    return _wrapped_view