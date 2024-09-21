from django.db import models

# Create your models here.
class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)
        
    def __str__(self):
        return self.name
    
class Organization(models.Model):
    name = models.CharField(max_length=255)  # Organization name
    email = models.EmailField()               # Organization email
    address = models.TextField()               # Organization address
    phone_number = models.CharField(max_length=15)  # Organization phone number
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization')
    
    def __str__(self):
        return self.name
