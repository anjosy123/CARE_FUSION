# Generated by Django 5.1 on 2024-10-14 15:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_staff_options_alter_staff_managers_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='staff',
            name='must_change_password',
            field=models.BooleanField(default=False),
        ),
    ]
