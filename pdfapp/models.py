from django.db import models
import random

class Contact(models.Model):
    place = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    mobile_no = models.CharField(max_length=20)
    area = models.CharField(max_length=255)
    instrument = models.CharField(max_length=255)
    link = models.URLField(blank=True, null=True)
    remark = models.TextField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)  # Auto-add timestamp

    def __str__(self):
        return self.name
    

class User(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('user', 'User'),
        ('user1', 'User1'),
    ]

    name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=255)  # Store hashed passwords
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return f"{self.name} ({self.role})"
    

class VehiclePass(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15)
    vehicle_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=50)  # Removed choices to allow free input
    start_date = models.DateField()
    end_date = models.DateField()
    

    # ✅ Image Fields for Required Documents
    aadhaar_front = models.ImageField(upload_to="vehicle_photos/aadhaar_front/", null=True, blank=True)
    aadhaar_back = models.ImageField(upload_to="vehicle_photos/aadhaar_back/", null=True, blank=True)
    rc_book = models.ImageField(upload_to="vehicle_photos/rc_book/", null=True, blank=True)
    license_photo = models.ImageField(upload_to="vehicle_photos/license/", null=True, blank=True)
    reject_reason = models.TextField(blank=True, null=True)


    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    applied_at = models.DateField(auto_now_add=True)

    travel_reason = models.CharField(max_length=255)
    extra_name = models.CharField(max_length=255, blank=True, null=True)
    extra_place = models.CharField(max_length=255, blank=True, null=True)
    approved_by = models.IntegerField(null=True, blank=True)  # Stores Admin ID
    approved_date = models.DateField(null=True, blank=True)
    pass_no = models.IntegerField(blank=True, null=True)
    other_reason = models.CharField(max_length=255, blank=True, null=True)  # Optional field for extra details

    def generate_pass_no(self):
        # ✅ Get all existing pass numbers, convert them to integers, and sort them
        existing_numbers = [
            int(pass_no) for pass_no in VehiclePass.objects.values_list("pass_no", flat=True) if pass_no is not None
        ]
        existing_numbers.sort()  # Ensure the list is sorted

        # ✅ If no pass exists, start from 0001
        if not existing_numbers:
            return "0001"

        # ✅ Find the smallest missing number in sequence
        expected_no = 1  # Start from 1
        for num in existing_numbers:
            if num != expected_no:
                break  # Found a gap, use this number
            expected_no += 1

        # ✅ Format number as a 4-digit string (e.g., "0006")
        return f"{expected_no:04d}"  


                
    def __str__(self):
            return f"{self.name} - {self.vehicle_number} ({self.status})"
    
class GovVehiclePass(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    name = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15)
    vehicle_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=50)  # Removed choices to allow free input
    start_date = models.DateField()
    end_date = models.DateField()
    travel_reason = models.TextField()

    # ✅ Image Fields for Required Documents
    photo1 = models.ImageField(upload_to="vehicle_photos/Gov_letter/", null=True, blank=True)
    reject_reason = models.TextField(blank=True, null=True)


    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    applied_at = models.DateField(auto_now_add=True)

    travel_reason = models.CharField(max_length=255)
    extra_name = models.CharField(max_length=255, blank=True, null=True)
    
    approved_by = models.IntegerField(null=True, blank=True)  # Stores Admin ID
    approved_date = models.DateField(null=True, blank=True)
    pass_no = models.IntegerField(blank=True, null=True)
    # other_reason = models.CharField(max_length=255, blank=True, null=True)  # Optional field for extra details

    def generate_pass_no(self):
        # ✅ Get all existing pass numbers, convert them to integers, and sort them
        existing_numbers = [
            int(pass_no) for pass_no in VehiclePass.objects.values_list("pass_no", flat=True) if pass_no is not None
        ]
        existing_numbers.sort()  # Ensure the list is sorted

        # ✅ If no pass exists, start from 0001
        if not existing_numbers:
            return "0001"

        # ✅ Find the smallest missing number in sequence
        expected_no = 1  # Start from 1
        for num in existing_numbers:
            if num != expected_no:
                break  # Found a gap, use this number
            expected_no += 1

        # ✅ Format number as a 4-digit string (e.g., "0006")
        return f"{expected_no:04d}"  


                
    def __str__(self):
            return f"{self.name} - {self.vehicle_number} ({self.status})"

class PressPass(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Rejected', 'Rejected'),
        ('Approved', 'Approved'),
    ]

    name = models.CharField(max_length=255)
    press_channel = models.CharField(max_length=255)
    vehicle_number = models.CharField(max_length=50)
    vehicle_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    press_id_card = models.ImageField(upload_to='press_id_cards/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"{self.name} - {self.press_channel}"