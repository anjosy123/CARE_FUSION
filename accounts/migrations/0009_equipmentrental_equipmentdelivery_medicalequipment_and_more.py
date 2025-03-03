# Generated by Django 5.1 on 2025-02-16 04:10

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_patientvisitrecord_priority_score_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='EquipmentRental',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('status', models.CharField(choices=[('PENDING', 'Pending Approval'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('ACTIVE', 'Active'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('security_deposit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('payment_status', models.CharField(default='PENDING', max_length=20)),
                ('razorpay_order_id', models.CharField(blank=True, max_length=100)),
                ('razorpay_payment_id', models.CharField(blank=True, max_length=100)),
                ('delivery_address', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='EquipmentDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('ASSIGNED', 'Assigned'), ('IN_PROGRESS', 'In Progress'), ('DELIVERED', 'Delivered'), ('FAILED', 'Failed')], default='PENDING', max_length=20)),
                ('assigned_at', models.DateTimeField(blank=True, null=True)),
                ('delivery_date', models.DateTimeField(blank=True, null=True)),
                ('delivery_notes', models.TextField(blank=True)),
                ('signature_image', models.ImageField(blank=True, null=True, upload_to='delivery_signatures/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('volunteer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.staff')),
                ('rental', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='accounts.equipmentrental')),
            ],
        ),
        migrations.CreateModel(
            name='MedicalEquipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('equipment_type', models.CharField(max_length=100)),
                ('condition', models.CharField(choices=[('NEW', 'New'), ('EXCELLENT', 'Excellent'), ('GOOD', 'Good'), ('FAIR', 'Fair')], max_length=20)),
                ('status', models.CharField(choices=[('AVAILABLE', 'Available'), ('RENTED', 'Rented'), ('MAINTENANCE', 'Under Maintenance'), ('RETIRED', 'Retired')], default='AVAILABLE', max_length=20)),
                ('rental_price_per_day', models.DecimalField(decimal_places=2, max_digits=10)),
                ('security_deposit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('serial_number', models.CharField(max_length=100, unique=True)),
                ('maintenance_history', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='equipment', to='accounts.organizations')),
            ],
        ),
        migrations.AddField(
            model_name='equipmentrental',
            name='equipment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.medicalequipment'),
        ),
    ]
