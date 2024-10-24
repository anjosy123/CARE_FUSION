# Generated by Django 5.1 on 2024-10-20 13:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0023_alter_teamdashboard_staff_alter_teamdashboard_team_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizations',
            name='teams',
            field=models.ManyToManyField(blank=True, related_name='team_organizations', to='accounts.team'),
        ),
        migrations.AlterField(
            model_name='team',
            name='members',
            field=models.ManyToManyField(related_name='staff_teams', to='accounts.staff'),
        ),
        migrations.AlterField(
            model_name='team',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='organization_teams', to='accounts.organizations'),
        ),
    ]
