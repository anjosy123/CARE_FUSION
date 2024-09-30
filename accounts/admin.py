from django.contrib import admin
<<<<<<< HEAD
from accounts.models import Organizations 
# Register your models here.

admin.site.register(Organizations)
=======
from accounts.models import Organizations,Contact
# Register your models here.

admin.site.register(Organizations)
admin.site.register(Contact)
>>>>>>> c836822a135e3af93d885c499392c758f76484f1
