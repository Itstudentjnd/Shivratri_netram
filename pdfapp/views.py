import csv
from datetime import datetime, timezone
import zipfile
import openpyxl
import pandas as pd
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse
from .models import *
from .forms import PressPassForm, RegistrationForm, LoginForm, CSVUploadForm, VehiclePassForm, GovVehiclePassForm
import qrcode
import os
import io
from django.conf import settings
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.contrib.auth import logout
from PIL import Image, ImageDraw, ImageFont
from django.utils.timezone import now
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A5, landscape
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from itertools import chain

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
                    # 🔹 Store user data in session
                    request.session['user_id'] = user.id
                    request.session['user_name'] = user.name  # Store user name
                    request.session['mobile_no'] = user.mobile_no  # Store mobile no
                    request.session['role'] = user.role  # Store role

                    # messages.success(request, "✅ Login successful!")

                    if user.role == "admin":
                        return redirect("admin_vehicle_passes")
                    elif user.role == "user1":
                        return redirect("issue_gov_vehicle_pass")
                    else:
                        return redirect("issue_vehicle_pass")
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



def check_pass_status(request):
    if request.session.get("role") == "user":
        pass_status = None
        reject_reason = None  # Default None

        if request.method == "POST":
            # ✅ Extract input fields from the form
            state_code = request.POST.get("state_code", "").strip().upper()
            city_code = request.POST.get("city_code", "").strip().upper()
            series = request.POST.get("series", "").strip().upper()
            digits = request.POST.get("digits", "").strip()

            # ✅ Construct full vehicle number in proper format
            vehicle_number = f"{state_code}{city_code}{series}{digits}"

            try:
                vehicle_pass = VehiclePass.objects.get(vehicle_number=vehicle_number)
                pass_status = vehicle_pass.status
                reject_reason = vehicle_pass.reject_reason if pass_status == "rejected" else None  # Fetch reason only if rejected
            except VehiclePass.DoesNotExist:
                pass_status = "not_found"

        return render(request, "check_status.html", {
            "pass_status": pass_status,
            "reject_reason": reject_reason,  # ✅ Pass reject reason to template
        })
    return redirect(login_view)

def issue_vehicle_pass(request):
    if request.session.get("role") == "user":
        if request.method == "POST":
            # 🚗 Construct Vehicle Number
            vehicle_number = (
                request.POST.get("state_code", "").upper()
                + request.POST.get("city_code", "")
                + request.POST.get("series", "").upper()
                + request.POST.get("digits", "")
            )

            # 🚨 Check for Duplicate Vehicle Number
            if VehiclePass.objects.filter(vehicle_number=vehicle_number).exists():
                messages.error(request, f"🚨 આ વાહન નંબર ({vehicle_number}) માટે પહેલેથી જ અરજી થઈ ચૂકી છે!")
                return redirect("issue_vehicle_pass")

            # 📝 Process Form Data
            form = VehiclePassForm(request.POST, request.FILES)
            
            if form.is_valid():
                vehicle_pass = form.save(commit=False)
                vehicle_pass.vehicle_number = vehicle_number
                vehicle_pass.mobile_no = request.POST.get("mobile_no", "")

                # 📂 Handle File Uploads
                vehicle_pass.aadhaar_front = request.FILES.get("aadhaar_front")
                vehicle_pass.aadhaar_back = request.FILES.get("aadhaar_back")
                vehicle_pass.rc_book = request.FILES.get("rc_book")
                vehicle_pass.license_photo = request.FILES.get("license_photo")

                # 📌 Travel Reason Handling
                travel_reason = request.POST.get("travel_reason", "").strip()
                extra_name = request.POST.get("extra_name", "").strip()
                extra_place = request.POST.get("extra_place", "").strip()
                other_reason = request.POST.get("other_reason", "").strip()

                # 🛠 Fix: Ensure 'Other Reason' is not empty if selected
                if travel_reason == "other":
                    if not other_reason:
                        messages.error(request, "❌ જો તમે 'અન્ય' પસંદ કરો છે, તો કૃપા કરીને કારણ દાખલ કરો!")
                        return redirect("issue_vehicle_pass")
                    final_reason = other_reason
                    extra_name, extra_place = "", ""  # 🔥 Clear extra fields for 'Other' selection
                else:
                    final_reason = travel_reason

                vehicle_pass.travel_reason = final_reason
                vehicle_pass.extra_name = extra_name
                vehicle_pass.extra_place = extra_place

                # 🚀 Set Status & Date
                vehicle_pass.status = "pending"
                vehicle_pass.applied_at = timezone.now()

                vehicle_pass.save()

                # ✅ Format Date & Time for Display
                formatted_datetime = vehicle_pass.applied_at.strftime("%d-%m-%Y %I:%M %p")
                messages.success(request, f"✅ વાહન પાસ પર સફળતાપૂર્વક સબમિટ થય ગયેલ છે! જાણકારી માટે સાઇટ ચકાસતા રહો.")
                return redirect("issue_vehicle_pass")

            else:
                print(form.errors)  # 🐞 Debugging step: Print form errors in console
                messages.error(request, "❌ કૃપા કરીને બધી વિગતો સાચી રીતે ભરો.")

        else:
            form = VehiclePassForm()

        return render(request, "issue_vehicle_pass.html", {"form": form})
    return redirect(login_view)


def issue_gov_vehicle_pass(request):
    if request.session.get("role") == "user1":
        if request.method == "POST":
            # 🚗 Construct Vehicle Number
            vehicle_number = (
                request.POST.get("state_code", "").upper()
                + request.POST.get("city_code", "")
                + request.POST.get("series", "").upper()
                + request.POST.get("digits", "")
            )

            # 🚨 Check for Duplicate Vehicle Number
            if GovVehiclePass.objects.filter(vehicle_number=vehicle_number).exists():
                messages.error(request, f"🚨 આ વાહન નંબર ({vehicle_number}) માટે પહેલેથી જ અરજી થઈ ચૂકી છે!")
                return redirect("issue_vehicle_pass")

            # 📝 Process Form Data
            form = GovVehiclePassForm(request.POST, request.FILES)
            
            if form.is_valid():
                vehicle_pass = form.save(commit=False)
                vehicle_pass.vehicle_number = vehicle_number
                vehicle_pass.mobile_no = request.POST.get("mobile_no", "")

                # 📂 Handle File Uploads
                vehicle_pass.photo1 = request.FILES.get("photo1")
                # 📌 Travel Reason Handling
                travel_reason = request.POST.get("travel_reason", "").strip()
                extra_name = request.POST.get("extra_name", "").strip()
                
                

                # 🛠 Fix: Ensure 'Other Reason' is not empty if selected
            
                
                final_reason = travel_reason

                vehicle_pass.travel_reason = final_reason
                vehicle_pass.extra_name = extra_name
                

                # 🚀 Set Status & Date
                vehicle_pass.status = "pending"
                vehicle_pass.applied_at = timezone.now()

                vehicle_pass.save()

                # ✅ Format Date & Time for Display
                formatted_datetime = vehicle_pass.applied_at.strftime("%d-%m-%Y %I:%M %p")
                messages.success(request, f"✅ વાહન પાસ પર સફળતાપૂર્વક સબમિટ થય ગયેલ છે! જાણકારી માટે સાઇટ ચકાસતા રહો.")
                return redirect("issue_gov_vehicle_pass")

            else:
                print(form.errors)  # 🐞 Debugging step: Print form errors in console
                messages.error(request, "❌ કૃપા કરીને બધી વિગતો સાચી રીતે ભરો.")

        else:
            form = GovVehiclePassForm()

        return render(request, "issue_gov_vehicle_pass.html", {"form": form})
    return redirect(login_view)



# ✅ Admin Panel to View Requests
def admin_vehicle_passes(request):
    if request.session.get("role") == "admin":
        # 🔹 Fetch records from both tables
        vehicle_passes = VehiclePass.objects.all()
        gov_vehicle_passes = GovVehiclePass.objects.all()

        # 🔹 Merge both querysets & order by latest entry
        passes = sorted(
            chain(vehicle_passes, gov_vehicle_passes), 
            key=lambda obj: obj.id, 
            reverse=True
        )

        total_requests = len(passes)  # Total vehicle pass requests

        # 🔹 Get user details for approval tracking
        for pass_obj in passes:
            if pass_obj.approved_by:  # If approved/rejected by someone
                user = User.objects.filter(id=pass_obj.approved_by).first()
                pass_obj.approved_by_name = user.name if user else "Unknown"

        return render(request, 'admin_vehicle_passes.html', {'passes': passes, 'total_requests': total_requests})

    return redirect(login_view)

def approved_gov(request):
    if request.session.get("role") == "user1":
        # 🔹 Fetch records from both tables

        gov_vehicle_passes = GovVehiclePass.objects.all()

        # 🔹 Merge both querysets & order by latest entry
        passes =  gov_vehicle_passes

        total_requests = len(passes)  # Total vehicle pass requests

        # 🔹 Get user details for approval tracking
        for pass_obj in passes:
            if pass_obj.approved_by:  # If approved/rejected by someone
                user = User.objects.filter(id=pass_obj.approved_by).first()
                pass_obj.approved_by_name = user.name if user else "Unknown"

        return render(request, 'approved_gov.html', {'passes': passes, 'total_requests': total_requests})

    return redirect(login_view)

def approved_private(request):
    if request.session.get("role") == "user":
        # 🔹 Fetch records from both tables

        vehicle_passes = VehiclePass.objects.all()

        # 🔹 Merge both querysets & order by latest entry
        passes =  vehicle_passes

        total_requests = len(passes)  # Total vehicle pass requests

        # 🔹 Get user details for approval tracking
        for pass_obj in passes:
            if pass_obj.approved_by:  # If approved/rejected by someone
                user = User.objects.filter(id=pass_obj.approved_by).first()
                pass_obj.approved_by_name = user.name if user else "Unknown"

        return render(request, 'approved_private.html', {'passes': passes, 'total_requests': total_requests})

    return redirect(login_view)

def export_vehicle_passes(request):
    # ✅ Create a new Excel workbook and sheet
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Vehicle Passes"

    # ✅ Add Headers (Gujarati & English Supported)
    headers = ["ID", "Vehicle Number", "Applicant Name", 
               "Mobile", "Vehicle Type", "Reason", 
               "Extra Name", "Extra Place", 
               "Start Date", "End Date", "Applied At", 
               "Status", "Approved Date", "Approved By", 
               "Rejection Reason"]
    sheet.append(headers)

    # ✅ Fetch all passes
    passes = VehiclePass.objects.all()
    
    # ✅ Create a dictionary to cache user names (avoid multiple DB queries)
    user_cache = {}

    for p in passes:
        # 🔹 Get Approved By Name
        approved_by_name = ""
        if p.approved_by:  # If approved_by is not None
            if p.approved_by in user_cache:
                approved_by_name = user_cache[p.approved_by]  # Get from cache
            else:
                user = User.objects.filter(id=p.approved_by).first()  # Fetch User
                approved_by_name = user.name if user else ""  # Get Name or Empty
                user_cache[p.approved_by] = approved_by_name  # Store in cache

        # 🔹 Append Data to Excel
        sheet.append([
            p.id, p.vehicle_number, p.name, p.mobile_no, p.vehicle_type, 
            p.travel_reason, p.extra_name, p.extra_place, 
            p.start_date, p.end_date, 
            p.applied_at.strftime("%d-%m-%Y %I:%M %p"), 
            p.status, 
            p.approved_date if p.approved_date else "", 
            approved_by_name,  # ✅ Show Name Instead of ID
            p.reject_reason if p.status == "rejected" else ""
        ])

    # ✅ Set Response Headers for Excel Download
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="vehicle_passes.xlsx"'
    
    # ✅ Save the workbook to response
    workbook.save(response)
    return response

def export_gov_vehicle_passes(request):
    # ✅ Create a new Excel workbook and sheet
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Vehicle Passes"

    # ✅ Add Headers (Gujarati & English Supported)
    headers = ["ID", "Vehicle Number", "Applicant Name", 
               "Mobile", "Vehicle Type", "Reason", 
               "Extra Name", "Extra Place", 
               "Start Date", "End Date", "Applied At", 
               "Status", "Approved Date", "Approved By", 
               "Rejection Reason"]
    sheet.append(headers)

    # ✅ Fetch all passes
    passes = GovVehiclePass.objects.all()
    
    # ✅ Create a dictionary to cache user names (avoid multiple DB queries)
    user_cache = {}

    for p in passes:
        # 🔹 Get Approved By Name
        approved_by_name = ""
        if p.approved_by:  # If approved_by is not None
            if p.approved_by in user_cache:
                approved_by_name = user_cache[p.approved_by]  # Get from cache
            else:
                user = User.objects.filter(id=p.approved_by).first()  # Fetch User
                approved_by_name = user.name if user else ""  # Get Name or Empty
                user_cache[p.approved_by] = approved_by_name  # Store in cache

        # 🔹 Append Data to Excel
        sheet.append([
            p.id, p.vehicle_number, p.name, p.mobile_no, p.vehicle_type, 
            p.travel_reason, p.extra_name, 
            p.start_date, p.end_date, 
            p.applied_at.strftime("%d-%m-%Y %I:%M %p"), 
            p.status, 
            p.approved_date if p.approved_date else "", 
            approved_by_name,  # ✅ Show Name Instead of ID
            p.reject_reason if p.status == "rejected" else ""
        ])

    # ✅ Set Response Headers for Excel Download
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="vehicle_passes.xlsx"'
    
    # ✅ Save the workbook to response
    workbook.save(response)
    return response

def update_pass_status(request, pass_id, status):
    vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)

    if status not in ["approved", "rejected"]:
        return HttpResponse("❌ Invalid Status!", status=400)
    admin_id = request.session.get("user_id")  # Get admin ID from session

    # ✅ Handle Rejection with Reason
    if status == "rejected":
        if request.method == "POST":
            reject_reason = request.POST.get("reject_reason", "").strip()
            if not reject_reason:
                messages.error(request, "❌ Please provide a reason for rejection!")
                return redirect("admin_vehicle_passes")  # Redirect back to admin panel

            vehicle_pass.status = "rejected"
            vehicle_pass.reject_reason = reject_reason
            vehicle_pass.approved_by = admin_id  # Save rejection reason
            vehicle_pass.save()

            messages.success(request, "❌ Vehicle Pass Rejected Successfully!")
            return redirect("admin_vehicle_passes")  # Redirect after rejection

        # If GET request for rejection, show error
        messages.error(request, "❌ Invalid request method for rejection!")
        return redirect("admin_vehicle_passes")

    # ✅ If approved, update status
    if status == "approved":
        vehicle_pass.status = "approved"
        vehicle_pass.reject_reason = ""  # Clear rejection reason
        vehicle_pass.approved_by = admin_id 
        vehicle_pass.approved_date = now().date()
        if not vehicle_pass.pass_no:  # ✅ Only generate if not assigned yet
            vehicle_pass.pass_no = vehicle_pass.generate_pass_no()   # ✅ Store Current Date
        vehicle_pass.save()
        # return generate_pass_image(vehicle_pass)  # Generates the pass and returns response

    return redirect("admin_vehicle_passes") 

def generate_pass_image(request, pass_id):
    # ✅ Get the pass record
    vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)

    # ✅ Ensure pass is approved
    if vehicle_pass.status != "approved":
        return JsonResponse({"error": "Pass is not approved yet."}, status=400)

    # ✅ Generate Pass Image (A5 Landscape)
    image_size = (2480, 1748)  # A5 Size
    img = Image.new("RGB", image_size, "white")
    draw = ImageDraw.Draw(img)

    # ✅ Load Gujarati Font
    def load_font(font_name, size):
        font_path = os.path.join(settings.MEDIA_ROOT, "font", font_name)
        try:
            return ImageFont.truetype(font_path, size)
        except IOError:
            return ImageFont.truetype("arial.ttf", size)

    # 🔹 Use "Noto Sans Gujarati" for proper rendering
    font_title = load_font("NotoSansGujarati-Bold.ttf", 90)  # Main Title
    font_main_head = load_font("NotoSansGujarati-Bold.ttf", 120)  # Main Title
    font_normal = load_font("NotoSansGujarati-Regular.ttf", 50)  # Uniform Font Size
    font_bold = load_font("NotoSansGujarati-Bold.ttf", 50)  # Uniform Font Size

    # ✅ Header Section
    draw.text((400, 80), "જૂનાગઢ પોલીસ - મહાશિવરાત્રી મેળો ૨૦૨૫", fill="black", font=font_main_head)
    
    # 🔹 Add a Bold Line Below the Header
    draw.line([(100, 260), (2380, 260)], fill="black", width=6)

    formatted_date = vehicle_pass.approved_date.strftime("%d-%m-%Y")

    draw.text((1900, 280), f"પાસ નંબર: {vehicle_pass.pass_no}/2025", fill="black", font=font_bold)
    draw.text((1900, 380), f"ઈશ્યુ તારીખ: {formatted_date}", fill="black", font=font_bold)

    # ✅ Police Logo
    logo_path = os.path.join(settings.MEDIA_ROOT, "junagadh_police.png")
    if os.path.exists(logo_path):
        police_logo = Image.open(logo_path).convert("RGBA")
        police_logo = police_logo.resize((230, 230))
        img.paste(police_logo, (100, 20), police_logo)

    # ✅ QR Code Generation
    qr_data = f"""
    નામ: {vehicle_pass.name}
    મોબાઇલ: {vehicle_pass.mobile_no}
    વાહન નંબર: {vehicle_pass.vehicle_number}
    વાહન પ્રકાર: {vehicle_pass.vehicle_type}
    શરુઆત તારીખ: {vehicle_pass.start_date}
    અંતિમ તારીખ: {vehicle_pass.end_date}
    """
    
    qr = qrcode.QRCode(
        version=5, 
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=10,  # Increased for better resolution
        border=2
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # ✅ Center Image in QR Code
    center_img_path = os.path.join(settings.MEDIA_ROOT, "GUJARAT POLICE LOGO PNG.png")
    if os.path.exists(center_img_path):
        center_img = Image.open(center_img_path).convert("RGBA")
        qr_size = qr_img.size[0]

        # Reduce overlay image size to ensure proper scanning
        center_img = center_img.resize((int(qr_size // 3), int(qr_size // 3)))  

        # ✅ Paste Center Image in QR Code
        qr_x = (qr_img.size[0] - center_img.size[0]) // 2
        qr_y = (qr_img.size[1] - center_img.size[1]) // 2
        qr_img.paste(center_img, (qr_x, qr_y), center_img)

    # ✅ Paste QR Code on Pass
    qr_resized = qr_img.resize((500, 500))  # Increased size to make scanning easier
    img.paste(qr_resized, (1200, 1050))  # Adjusted position

    # ✅ Function to Draw Dotted Lines
    def draw_dotted_line(draw, start_x, start_y, end_x, dot_spacing=20, dot_length=12):
        x = start_x
        while x < end_x:
            draw.line([(x, start_y), (x + dot_length, start_y)], fill="black", width=3)
            x += dot_spacing  

    # ✅ Pass Title
    draw.text((850, 280), "વાહન પ્રવેશ પરવાનગી", fill="black", font=font_title)

    # ✅ Vehicle Entry Details with Dotted Lines
    fields = [
        ("તારીખ:", vehicle_pass.start_date, 200, 500),
        ("થી", "", 1000, 500),
        ("તારીખ:", vehicle_pass.end_date, 1200, 500),
        ("વાહન નંબર:", vehicle_pass.vehicle_number, 200, 650),
        ("વાહન પ્રકાર:", vehicle_pass.vehicle_type, 1200, 650),
        ("નામ:", vehicle_pass.name, 200, 800),
        ("મોબાઇલ નંબર:", vehicle_pass.mobile_no, 1200, 800),
        ("પ્રવાસનું કારણ:", vehicle_pass.travel_reason, 200, 950),
        (f"{vehicle_pass.travel_reason} નું નામ:", vehicle_pass.travel_reason, 1200, 950),
    ]

    for label, value, x, y in fields:
        draw.text((x, y), label, fill="black", font=font_bold)  # Bold Label
        draw.text((x + 400, y), f"{value}", fill="black", font=font_normal)  # Normal Value
        draw_dotted_line(draw, x, y + 60, x + 800)  # Dotted Line

    # ✅ Police Officer Signature Section
    draw.text((1950, 1400), "પોલીસ અધિક્ષક", fill="black", font=font_bold)
    draw.text((2000, 1460), "જૂનાગઢ વતી,", fill="black", font=font_bold)

    # ✅ Rules Section with Bullet Points
    draw.line([(50, 1550), (2430, 1550)], fill="black", width=4)
    draw.text((100, 1600), "• પાસનું ડુપ્લીકેશન કે કલર ફોટોકોપી કરાવી તેનો ઉપયોગ કરવો ગુનાહિત છે.", fill="black", font=font_bold)
    draw.text((100, 1660), "• ફરજ પરના પોલીસ કર્મચારીના વાસ્તવિક હુકમને આધિન રહેવું ફરજિયાત છે.", fill="black", font=font_bold)

    # ✅ Save Image
    vehicle_pass_folder = os.path.join(settings.MEDIA_ROOT, "vehicle-pass")
    os.makedirs(vehicle_pass_folder, exist_ok=True)
    image_path = os.path.join(vehicle_pass_folder, f'{vehicle_pass.vehicle_number}.png')
    img.save(image_path)

    # ✅ Ask user for position choice (frontend should send this choice in request)
    position = request.GET.get("position", "top")  # Default to "top" if not provided

    # ✅ Create A4 Portrait PDF and place A5 pass image inside it
    pdf_path = os.path.join(vehicle_pass_folder, f"{vehicle_pass.vehicle_number}.pdf")
    pdf_canvas = canvas.Canvas(pdf_path, pagesize=A4)

    # ✅ Set image position based on user choice
    if position == "top":
        pdf_canvas.drawImage(ImageReader(image_path), 0, 420, width=595, height=420)  # Top Half
    elif position == "bottom":
        pdf_canvas.drawImage(ImageReader(image_path), 0, 0, width=595, height=420)  # Bottom Half
    else:
        return JsonResponse({"error": "Invalid position. Use 'top' or 'bottom'."}, status=400)

    # ✅ Save PDF
    pdf_canvas.showPage()
    pdf_canvas.save()

    # ✅ Return PDF Response
    with open(pdf_path, "rb") as pdf_file:
        response = HttpResponse(pdf_file.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{vehicle_pass.vehicle_number}.pdf"'
        return response

def download_images(request, pass_id):
    # ✅ Get the vehicle pass record
    vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)

    # ✅ Get all images associated with the pass
    image_fields = ['aadhaar_front', 'aadhaar_back', 'rc_book', 'license_photo']
    image_paths = [getattr(vehicle_pass, field).path for field in image_fields if getattr(vehicle_pass, field)]

    if not image_paths:
        return HttpResponse("No images available for this pass.", content_type="text/plain")

    # ✅ Define ZIP file name (use vehicle number)
    zip_filename = f"{vehicle_pass.vehicle_number}.zip"
    zip_filepath = os.path.join(settings.MEDIA_ROOT, "temp_zips", zip_filename)

    # ✅ Ensure temp_zips folder exists
    os.makedirs(os.path.dirname(zip_filepath), exist_ok=True)

    # ✅ Create a ZIP file and add images
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for image_path in image_paths:
            zip_file.write(image_path, os.path.basename(image_path))  # Save inside ZIP

    # ✅ Serve the ZIP file for download
    with open(zip_filepath, 'rb') as zip_file:
        response = HttpResponse(zip_file.read(), content_type="application/zip")
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    
    # ✅ Delete the ZIP after serving (optional for cleanup)
    os.remove(zip_filepath)

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
    
