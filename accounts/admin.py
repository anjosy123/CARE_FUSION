from django.contrib import admin
from accounts.models import Contact
from django.contrib.auth.admin import UserAdmin
from .models import User, Organizations
# Register your models here.

admin.site.register(User, UserAdmin)
admin.site.register(Organizations)
admin.site.register(Contact)
