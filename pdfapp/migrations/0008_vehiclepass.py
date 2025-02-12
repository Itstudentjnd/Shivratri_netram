# Generated by Django 4.2.7 on 2025-02-11 07:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pdfapp', '0007_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='VehiclePass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('mobile_no', models.CharField(max_length=15)),
                ('vehicle_number', models.CharField(max_length=20, unique=True)),
                ('vehicle_type', models.CharField(max_length=50)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('travel_reason', models.TextField()),
                ('photo', models.ImageField(upload_to='vehicle_photos/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('applied_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
