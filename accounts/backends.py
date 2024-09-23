from django.contrib.auth.backends import BaseBackend
from .models import Organizations

class OrganizationBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            org_user = Organizations.objects.get(org_username=username)
            if org_user.check_password(password):
                return org_user
        except Organizations.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Organizations.objects.get(pk=user_id)
        except Organizations.DoesNotExist:
            return None
