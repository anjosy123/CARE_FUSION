# Generated by Django 5.1 on 2024-12-16 06:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_teamnotification'),
    ]

    operations = [
        migrations.AddField(
            model_name='teamnotification',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='accounts.organizations'),
        ),
        migrations.AlterField(
            model_name='teamnotification',
            name='notification_type',
            field=models.CharField(choices=[('message', 'New Message'), ('request', 'New Request'), ('update', 'Status Update')], max_length=20),
        ),
        migrations.AlterField(
            model_name='teamnotification',
            name='recipient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='accounts.staff'),
        ),
        migrations.AlterField(
            model_name='teamnotification',
            name='team',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='accounts.team'),
        ),
    ]