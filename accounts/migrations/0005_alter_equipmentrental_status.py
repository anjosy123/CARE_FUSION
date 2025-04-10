# Generated by Django 5.1.6 on 2025-03-18 01:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_patientvisitrecord_patient_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equipmentrental',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('ACTIVE', 'Active'), ('END', 'Ended'), ('COMPLETED', 'Completed'), ('REJECTED', 'Rejected')], default='PENDING', max_length=20),
        ),
    ]
