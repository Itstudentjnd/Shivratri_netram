import pandas as pd
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse
from .models import *
from .forms import PressPassForm, RegistrationForm, LoginForm, CSVUploadForm, VehiclePassForm
import qrcode
import os
import io
from django.conf import settings
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.contrib.auth import logout
from PIL import Image, ImageDraw, ImageFont

# ✅ Login View
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            mobile_no = form.cleaned_data['mobile_no']
            password = form.cleaned_data['password']
            user = User.objects.filter(mobile_no=mobile_no).first()

            if user:
                # ✅ Check both hashed and plain text passwords
                if check_password(password, user.password) or password == user.password:
                    request.session['user_id'] = user.id
                    request.session['role'] = user.role
                    # messages.success(request, "✅ Login successful!")

                    if user.role == "admin":
                        return redirect("admin_vehicle_passes")
                    else:
                        return redirect("index")
                else:
                    messages.error(request, "❌ Invalid password!")
            else:
                messages.error(request, "❌ User not found!")

    form = LoginForm()
    return render(request, "login.html", {"form": form})

# ✅ Logout View
def logout_view(request):
    logout(request)  # ✅ Correctly logs out the user
    request.session.flush()  # Clear session data
    messages.success(request, "✅ Logged out successfully!")
    return redirect("login_view")  # Redirect to login page


# ✅ User Page (Restricted)
def index(request):
    return render(request, "index.html")

def check_status(request):
    pass_status = None

    if request.method == "POST":
        vehicle_number = request.POST.get("vehicle_number")

        # Check in VehiclePass model
        vehicle_pass = VehiclePass.objects.filter(vehicle_number=vehicle_number).first()

        # Check in PressPass model if not found in VehiclePass
        press_pass = PressPass.objects.filter(vehicle_number=vehicle_number).first() if not vehicle_pass else None

        if vehicle_pass:
            pass_status = vehicle_pass.status  # Assuming status field: 'approved', 'rejected', 'pending'
        elif press_pass:
            pass_status = press_pass.status  # Same status field in PressPass
        else:
            pass_status = "not_found"

    return render(request, "check_status.html", {"pass_status": pass_status})


def issue_vehicle_pass(request):
    if request.method == "POST":
        form = VehiclePassForm(request.POST, request.FILES)
        
        if form.is_valid():
            # ✅ Concatenate vehicle number parts before saving
            vehicle_number = (
                request.POST.get("state_code", "").upper()
                + request.POST.get("city_code", "")
                + request.POST.get("series", "").upper()
                + request.POST.get("digits", "")
            )

            # ✅ Create the object but do NOT save it yet
            vehicle_pass = form.save(commit=False)
            vehicle_pass.vehicle_number = vehicle_number  # Assign vehicle number
            
            # ✅ Assign uploaded files
            vehicle_pass.aadhaar_front = request.FILES.get("aadhaar_front", None)
            vehicle_pass.aadhaar_back = request.FILES.get("aadhaar_back", None)
            vehicle_pass.rc_book = request.FILES.get("rc_book", None)
            vehicle_pass.license_photo = request.FILES.get("license_photo", None)
            
            vehicle_pass.status = "pending"  # Default status
            vehicle_pass.save()  # ✅ Save the record in MySQL

            # messages.success(request, "✅ તમારું પાસ ઈશ્યુ થઈ ગયું છે!")
            return redirect("index")
        else:
            messages.error(request, "❌ કૃપા કરીને બધી વિગતો સાચી રીતે ભરો.")
    
    else:
        form = VehiclePassForm()

    return render(request, "issue_vehicle_pass.html", {"form": form})

# ✅ Admin Panel to View Requests
def admin_vehicle_passes(request):
    if request.session.get("role") == "admin":
        passes = VehiclePass.objects.all().order_by('-id')  # Fetch all records, latest first
        return render(request, 'admin_vehicle_passes.html', {'passes': passes})
    return HttpResponse("❌ Access Denied! Admins only.", status=403)

def update_pass_status(request, pass_id, status):
        

        vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)

        if status not in ["approved", "rejected"]:
            return HttpResponse("❌ Invalid Status!", status=400)

        # ✅ Update Status
        vehicle_pass.status = status
        vehicle_pass.save()
        
        messages.success(request, f"✅ Vehicle Pass **{status.capitalize()}** Successfully!")

        # ✅ If approved, generate the pass image
        if status == "approved":
            return generate_pass_image(vehicle_pass)

        return redirect("admin_vehicle_passes")  # Redirect if not generating image


def generate_pass_image(vehicle_pass):
    """Generate a professional Gujarat Police vehicle pass (A5 Landscape)."""

    # ✅ Set Image Size (A5 Landscape: 2480x1748 pixels)
    image_size = (2480, 1748)
    img = Image.new("RGB", image_size, "white")  # White background
    draw = ImageDraw.Draw(img)

    # ✅ Load Gujarati Font (Noto Sans Gujarati for proper rendering)
    def load_font(font_name, size):
        """Load a proper Unicode font that supports Gujarati."""
        font_path = os.path.join("media", "font", font_name)
        try:
            font = ImageFont.truetype(font_path, size)
            return font
        except IOError:
            return ImageFont.truetype("arial.ttf", size)  # Fallback

    # 🔹 Use "Noto Sans Gujarati" for proper rendering
    font_title = load_font("NotoSansGujarati-Bold.ttf", 85)  # Main Title
    font_subtitle = load_font("NotoSansGujarati-Regular.ttf", 65)  # Subtitle
    font_details = load_font("NotoSansGujarati-Regular.ttf", 50)  # Details
    font_small = load_font("NotoSansGujarati-Regular.ttf", 40)  # Smaller text
    font_rules = load_font("NotoSansGujarati-Regular.ttf", 38)  # Rules Section

    # ✅ Blue Header for Official Look
    draw.rectangle([(0, 0), (2480, 220)], fill="#003366")  # Blue Top Header
    draw.text((850, 60), "જૂનાગઢ પોલીસ - મહાશિવરાત્રી મેળો ૨૦૨૫", fill="white", font=font_title)

    # ✅ Load & Position Police Logo
    logo_path = os.path.join("media", "GUJARAT POLICE LOGO PNG.png")
    if os.path.exists(logo_path):
        police_logo = Image.open(logo_path).resize((180, 180))
        img.paste(police_logo, (100, 20))  # Inside Blue Header (Left)

    # ✅ QR Code Generation (Centered)
    qr_data = f"""
    વાહન પરવાનગી ID: {vehicle_pass.id}
    નામ: {vehicle_pass.name}
    મોબાઇલ: {vehicle_pass.mobile_no}
    વાહન નંબર: {vehicle_pass.vehicle_number}
    વાહન પ્રકાર: {vehicle_pass.vehicle_type}
    શરુઆત: {vehicle_pass.start_date}
    અંતિમ: {vehicle_pass.end_date}
    """
    qr = qrcode.make(qr_data).resize((500, 500))
    img.paste(qr, (1850, 700))  # Bottom Right Side

    # ✅ Draw a Line Below Header for Separation
    draw.line([(50, 230), (2430, 230)], fill="black", width=5)

    # ✅ Pass Title
    draw.text((870, 300), "વાહન પ્રવેશ પરવાનગી", fill="black", font=font_title)

    # ✅ Date Section - Proper Alignment
    draw.text((200, 480), f"શરુઆત: {vehicle_pass.start_date}", fill="black", font=font_details)
    draw.text((1400, 480), f"અંતિમ: {vehicle_pass.end_date}", fill="black", font=font_details)

    # ✅ Vehicle Details - Structured Alignment
    draw.text((200, 600), f"વાહન નંબર: {vehicle_pass.vehicle_number}", fill="black", font=font_subtitle)
    draw.text((200, 720), f"વાહન પ્રકાર: {vehicle_pass.vehicle_type}", fill="black", font=font_subtitle)

    # ✅ Applicant Information - Clean Layout
    draw.text((200, 860), f"નામ: {vehicle_pass.name}", fill="black", font=font_details)
    draw.text((200, 980), f"મોબાઇલ: {vehicle_pass.mobile_no}", fill="black", font=font_details)
    draw.text((200, 1100), f"પ્રવાસનું કારણ: {vehicle_pass.travel_reason}", fill="black", font=font_details)

    # ✅ Police Officer Signature Section
    draw.text((1900, 1400), "પોલીસ અધિકારી", fill="black", font=font_subtitle)
    draw.text((1900, 1470), "જુનાગઢ પોલીસ", fill="black", font=font_subtitle)

    # ✅ Rules Section - Neatly Placed at the Bottom
    draw.line([(50, 1580), (2430, 1580)], fill="black", width=4)
    draw.text((100, 1620), "પાસનું ડુપ્લીકેશન કે કલર ઝેરોક્સ કરાવી તેનો ઉપયોગ કરવો ગુનાહિત છે.", fill="black", font=font_rules)
    draw.text((100, 1680), "ફરજ પરના પોલીસ કર્મચારીના વાસ્તવિક હુકમને આધિન રહેવું ફરજિયાત છે.", fill="black", font=font_rules)

    vehicle_pass_folder = os.path.join(settings.MEDIA_ROOT, "vehical-pass")
    os.makedirs(vehicle_pass_folder, exist_ok=True)
    image_path = os.path.join(vehicle_pass_folder, f'{vehicle_pass.vehicle_number}.png')

    img.save(image_path)
    # ✅ Save Image to Response
    response = HttpResponse(content_type="image/png")
    img.save(response, "PNG")
    return response

# def press_pass_form(request):
#     if request.method == "POST":
#         name = request.POST.get('name')
#         press_channel = request.POST.get('press_channel')

#         # Combine vehicle number fields
#         state_code = request.POST.get('state_code')
#         city_code = request.POST.get('city_code')
#         series = request.POST.get('series')
#         digits = request.POST.get('digits')
#         vehicle_number = f"{state_code.upper()}{city_code}{series.upper()}{digits}"


#         vehicle_type = request.POST.get('vehicle_type')
#         start_date = request.POST.get('start_date')
#         end_date = request.POST.get('end_date')
#         press_id_card = request.FILES.get('press_id_card')

#         # Create and save the object
#         try:
#             PressPass.objects.create(
#                 name=name,
#                 press_channel=press_channel,
#                 vehicle_number=vehicle_number,
#                 vehicle_type=vehicle_type,
#                 start_date=start_date,
#                 end_date=end_date,
#                 press_id_card=press_id_card
#             )
#             messages.success(request, "તમારું અરજી સફળતાપૂર્વક સબમિટ થયું છે!")
#             return redirect('index')  # Redirect to the same form page after success
#         except Exception as e:
#             messages.error(request, f"ભૂલ: {e}")

#     return render(request, 'press_pass_form.html')

# def issue_press_pass(request):
#     if request.session.get("role") == "admin":
#         records = PressPass.objects.all()
#         return render(request, 'issue_press_pass.html', {'records': records})
#     return HttpResponse("❌ Access Denied! Admins only.", status=403)

# def update_status(request, record_id, action):
#     if request.session.get("role") == "admin":
#         press_pass = get_object_or_404(PressPass, id=record_id)

#         if action == 'approve':
#             press_pass.status = 'approved'
#             press_pass.save()
#             generate_press_pass(record_id)  # Call the function to generate pass

#         elif action == 'reject':
#             press_pass.status = 'rejected'
#             press_pass.save()

#         return JsonResponse({'status': press_pass.status})
#     return HttpResponse("❌ Access Denied! Admins only.", status=403)

# def generate_press_pass(request,record_id):
    
#         record = PressPass.objects.get(id=record_id)

#         # ✅ Card Size: 3.88 in x 2.63 in (300 DPI)
#         width, height = 1164, 790  # Pixels at 300 DPI
#         img = Image.new('RGB', (width, height), color=(230, 230, 230))  # Light Grey Background for Better UI
#         draw = ImageDraw.Draw(img)

#         # ✅ Load Gujarat Police Logo
#         logo_path = os.path.join(settings.BASE_DIR, 'media', 'GUJARAT POLICE LOGO PNG.png')
#         if os.path.exists(logo_path):
#             logo = Image.open(logo_path).resize((150, 150))  # Resize Logo
#             img.paste(logo, (30, 20))  # Paste Logo at Top Left

#         # ✅ Load Gujarati Font (Ensure correct rendering)
#         font_path = os.path.join(settings.BASE_DIR, 'media', 'font', 'NotoSansGujarati-Bold.ttf')
#         if not os.path.exists(font_path):
#             font_path = os.path.join(settings.BASE_DIR, 'media', 'font', 'shruti.ttf')  # Fallback to Shruti
        
#         title_font = ImageFont.truetype(font_path, 80)  # Large font for "Junagadh Police"
#         sub_title_font = ImageFont.truetype(font_path, 60)  # Medium font for "Mahashivratri 2025"
#         pass_font = ImageFont.truetype(font_path, 50)  # Smaller font for "Press Media Pass"

#         # ✅ Add Titles in Gujarati (Aligned properly)
#         draw.text((width // 2 - 250, 50), "જુનાગઢ પોલીસ", fill="black", font=title_font)  # Large Text
#         draw.text((width // 2 - 230, 150), "મહાશિવરાત્રી 2025", fill="red", font=sub_title_font)  # Medium Text
#         draw.text((width // 2 - 220, 230), "PRESS MEDIA PASS", fill="blue", font=pass_font)  # Smaller Text

#         # ✅ Load Smaller Font for Details
#         details_font_path = os.path.join(settings.BASE_DIR, 'media', 'font', 'NotoSansGujarati-Regular.ttf')
#         if not os.path.exists(details_font_path):
#             details_font_path = os.path.join(settings.BASE_DIR, 'media', 'font', 'shruti.ttf')  # Fallback

#         details_font = ImageFont.truetype(details_font_path, 45)

#         # ✅ Add Press Pass Details in Gujarati with Proper Alignment
#         draw.text((50, 320), f"નામ: {record.name}", fill="black", font=details_font)
#         draw.text((50, 380), f"ચેનલ: {record.press_channel}", fill="black", font=details_font)
#         draw.text((50, 440), f"વાહન નં.: {record.vehicle_number}", fill="black", font=details_font)
#         draw.text((50, 500), f"પ્રકાર: {record.vehicle_type}", fill="black", font=details_font)
#         draw.text((50, 560), f"માન્યતા: {record.start_date} - {record.end_date}", fill="black", font=details_font)

#         # ✅ Larger QR Code for Verification
#         qr_data = f"નામ: {record.name}\nપ્રેસ ચેનલ: {record.press_channel}\nવાહન: {record.vehicle_number}\nપ્રકાર: {record.vehicle_type}\nમાન્યતા: {record.start_date} - {record.end_date}"
#         qr = qrcode.make(qr_data).resize((350, 350))  # Resize QR (Larger)
#         img.paste(qr, (800, 400))  # Place QR at Bottom Right

#         # ✅ Save Press Pass in "press-pass" Folder
#         press_pass_folder = os.path.join(settings.MEDIA_ROOT, "press-pass")
#         os.makedirs(press_pass_folder, exist_ok=True)
#         image_path = os.path.join(press_pass_folder, f'pass_{record.name}.png')
#         img.save(image_path)

#         # ✅ Provide Download Option
#         return image_path, f"Download your Press Pass: /media/press-pass/pass_{record.name}.png"
    
