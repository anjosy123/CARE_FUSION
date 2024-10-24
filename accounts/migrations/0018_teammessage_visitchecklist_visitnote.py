# Generated by Django 5.1 on 2024-10-19 18:22

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_remove_notification_user_notification_organization_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_messages', to='accounts.staff')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='accounts.team')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VisitChecklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pain_assessment', models.BooleanField(default=False)),
                ('medication_review', models.BooleanField(default=False)),
                ('symptom_management', models.BooleanField(default=False)),
                ('psychological_support', models.BooleanField(default=False)),
                ('family_education', models.BooleanField(default=False)),
                ('team_visit', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='checklist', to='accounts.teamvisit')),
            ],
        ),
        migrations.CreateModel(
            name='VisitNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.staff')),
                ('team_visit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visit_notes', to='accounts.teamvisit')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
