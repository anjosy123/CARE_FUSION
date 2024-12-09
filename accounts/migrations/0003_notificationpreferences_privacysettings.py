# Generated by Django 5.1 on 2024-12-10 16:18

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_remove_notification_staff_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationPreferences',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_enabled', models.BooleanField(default=True)),
                ('appointment_reminders', models.BooleanField(default=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'accounts_notificationpreferences',
            },
        ),
        migrations.CreateModel(
            name='PrivacySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('profile_visible', models.BooleanField(default=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='privacy_settings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
