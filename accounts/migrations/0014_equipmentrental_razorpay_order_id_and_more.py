# Generated by Django 5.1 on 2025-02-18 08:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_alter_equipmentrental_payment_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipmentrental',
            name='razorpay_order_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='equipmentrental',
            name='razorpay_payment_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='equipmentrental',
            name='razorpay_signature',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
