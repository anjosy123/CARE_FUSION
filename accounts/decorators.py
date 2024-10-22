from django.shortcuts import redirect
from django.contrib import messages
from django.utils.decorators import wraps

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

