from django.shortcuts import redirect
from django.contrib import messages
from django.utils.decorators import wraps
from django.contrib.auth.models import User
from functools import wraps
from .models import TeamDashboard, Organizations

def staff_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'staff_id' not in request.session:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')  # Redirect to your login page
        return view_func(request, *args, **kwargs)
    return wrapper

def organization_login_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if 'org_id' not in request.session:
            messages.error(request, "Please log in as an organization first.")
            return redirect('organizations_home')
            
        try:
            # Get the organization and attach it to the request
            organization = Organizations.objects.get(id=request.session['org_id'])
            request.organization = organization
            return view_func(request, *args, **kwargs)
        except Organizations.DoesNotExist:
            messages.error(request, "Organization not found.")
            return redirect('organizations_home')
            
    return _wrapped_view


def patient_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            messages.error(request, "Please login to continue.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

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