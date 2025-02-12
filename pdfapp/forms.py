from django import forms
from .models import User, VehiclePass, PressPass
from django.contrib.auth.hashers import make_password

class CSVUploadForm(forms.Form):
    file = forms.FileField()

class RegistrationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'mobile_no', 'password']
        widgets = {
            'password': forms.PasswordInput()
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.password = make_password(self.cleaned_data['password'])  # Hash Password
        user.role = 'user'  # Default role
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    mobile_no = forms.CharField(max_length=15)
    password = forms.CharField(widget=forms.PasswordInput)

class VehiclePassForm(forms.ModelForm):
    class Meta:
        model = VehiclePass
        fields = [
            "name", "mobile_no", "vehicle_type", "start_date", "end_date", 
            "travel_reason", "aadhaar_front", "aadhaar_back", "rc_book", "license_photo"
        ]  # Exclude "vehicle_number" since we create it manually

class PressPassForm(forms.ModelForm):
    class Meta:
        model = PressPass
        fields = ['name', 'press_channel', 'vehicle_number', 'vehicle_type', 'start_date', 'end_date', 'press_id_card']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }