# Generated by Django 5.1 on 2024-12-17 04:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_teammessage_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]