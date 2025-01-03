# Generated by Django 5.1 on 2024-12-16 06:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_alter_teammessage_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('MESSAGE', 'New Message'), ('URGENT', 'Urgent Message'), ('PATIENT_UPDATE', 'Patient Update'), ('VISIT_REPORT', 'Visit Report')], max_length=20)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.teammessage')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.staff')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.team')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
