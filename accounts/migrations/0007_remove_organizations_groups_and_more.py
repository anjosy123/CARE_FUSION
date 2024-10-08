# Generated by Django 5.1 on 2024-10-05 04:21

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_remove_servicerequest_request_date_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='organizations',
            name='groups',
        ),
        migrations.RemoveField(
            model_name='organizations',
            name='user_permissions',
        ),
        migrations.AddField(
            model_name='organizations',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='organizations',
            name='org_password',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='organizations',
            name='org_phone',
            field=models.CharField(max_length=15),
        ),
    ]
