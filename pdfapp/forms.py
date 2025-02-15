from django import forms
from .models import User, VehiclePass, PressPass, GovVehiclePass
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

class GovVehiclePassForm(forms.ModelForm):
    class Meta:
        model = GovVehiclePass
        fields = [
            "name", "mobile_no", "vehicle_type", "start_date", "end_date", 
            "travel_reason", "photo1"
        ]  # Exclude "vehicle_number" s

class PressPassForm(forms.ModelForm):
    class Meta:
        model = PressPass
        fields = ['name', 'press_channel', 'vehicle_number', 'vehicle_type', 'start_date', 'end_date', 'press_id_card']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class VehiclePassUpdateForm(forms.ModelForm):
    class Meta:
        model = VehiclePass
        fields = [
            "name", "mobile_no", "vehicle_number", "vehicle_type",
            "start_date", "end_date", "travel_reason",
            "extra_name", "extra_place", "other_reason"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "mobile_no": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "vehicle_number": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "vehicle_type": forms.Select(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full bg-white focus:ring focus:ring-blue-200"}),
            "start_date": forms.DateInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200", "type": "date"}),
            "travel_reason": forms.Select(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full bg-white focus:ring focus:ring-blue-200"}),
            "extra_name": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "extra_place": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "other_reason": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
        }

    def __init__(self, *args, **kwargs):
        super(VehiclePassUpdateForm, self).__init__(*args, **kwargs)
        self.fields["vehicle_type"].widget = forms.Select(choices=[
            ("2-Wheel", "2-Wheel"),
            ("3-Wheel", "3-Wheel"),
            ("4-Wheel", "4-Wheel"),
            ("heavy-vehicle", "heavy-vehicle"),  
        ])
    
    
        self.fields["travel_reason"].widget = forms.Select(choices=[
            ("અન્નક્ષેત્ર માટે", "અન્નક્ષેત્ર માટે"),
            ("આશ્રમ સેવા / પૂજા", "આશ્રમ સેવા / પૂજા"),
            ("વેપાર / રોજગાર માટે", "વેપાર / રોજગાર માટે"),
            ("ધર્મશાળા માટે", "ધર્મશાળા માટે"),
            ("અન્ય", "અન્ય"),
        ])

class GovVehiclePassUpdateForm(forms.ModelForm):
    class Meta:
        model = GovVehiclePass
        fields = [
            "name", "mobile_no", "vehicle_number", "vehicle_type",
            "start_date", "end_date", "travel_reason",
            "extra_name"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "mobile_no": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "vehicle_number": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            "vehicle_type": forms.Select(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full bg-white focus:ring focus:ring-blue-200"}),
            "start_date": forms.DateInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200", "type": "date"}),
            "travel_reason": forms.Select(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full bg-white focus:ring focus:ring-blue-200"}),
            "extra_name": forms.TextInput(attrs={"class": "border border-gray-300 rounded-lg p-3 w-full focus:ring focus:ring-blue-200"}),
            
        }

    def __init__(self, *args, **kwargs):
        super(GovVehiclePassUpdateForm, self).__init__(*args, **kwargs)
        self.fields["vehicle_type"].widget = forms.Select(choices=[
            ("2-Wheel", "2-Wheel"),
            ("3-Wheel", "3-Wheel"),
            ("4-Wheel", "4-Wheel"),
            ("heavy-vehicle", "heavy-vehicle"),  
        ])
    
    
        self.fields["travel_reason"].widget = forms.Select(choices=[
            ("સરકારી કામ માટે", "સરકારી કામ માટે"),
        ])