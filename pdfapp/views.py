import csv
from datetime import datetime, timezone
import zipfile
import openpyxl
import pandas as pd
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse, JsonResponse
from .models import *
from .forms import GovVehiclePassUpdateForm, PressPassForm, RegistrationForm, LoginForm, CSVUploadForm, VehiclePassForm, GovVehiclePassForm, VehiclePassUpdateForm
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
            mobile_no = form.cleaned_data["mobile_no"]
            password = form.cleaned_data["password"]
            user = User.objects.filter(mobile_no=mobile_no).first()

            if user:
                if check_password(password, user.password) or password == user.password:
                    active_sessions = request.session.get("active_users", {})

                    if str(mobile_no) in active_sessions:
                        messages.error(request, "❌ This mobile number is already logged in!")
                        return redirect("login_view")

                    # ✅ Store user data in session
                    request.session["user_id"] = user.id
                    request.session["user_name"] = user.name
                    request.session["mobile_no"] = user.mobile_no
                    request.session["role"] = user.role

                    # ✅ Track active logins
                    request.session["active_users"] = active_sessions
                    request.session["active_users"][str(mobile_no)] = user.id

                    # ✅ Store Last Activity Timestamp
                    request.session["last_activity"] = now().timestamp()  # Store current time in seconds

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
    mobile_no = request.session.get("mobile_no")

    if mobile_no:
        active_sessions = request.session.get("active_users", {})
        active_sessions.pop(str(mobile_no), None)  # Remove user from active list
        request.session["active_users"] = active_sessions  # Update session

    request.session.flush()  # Clear session
    return redirect("login_view")





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

            # 🔍 **Check in both tables**
            try:
                # ✅ First, check in GovVehiclePass
                vehicle_pass = GovVehiclePass.objects.get(vehicle_number=vehicle_number)
                pass_status = vehicle_pass.status
                reject_reason = vehicle_pass.reject_reason if pass_status == "rejected" else None
            except GovVehiclePass.DoesNotExist:
                try:
                    # ✅ If not found, check in VehiclePass
                    vehicle_pass = VehiclePass.objects.get(vehicle_number=vehicle_number)
                    pass_status = vehicle_pass.status
                    reject_reason = vehicle_pass.reject_reason if pass_status == "rejected" else None
                except VehiclePass.DoesNotExist:
                    pass_status = "not_found"

        return render(request, "check_status.html", {
            "pass_status": pass_status,
            "reject_reason": reject_reason,  # ✅ Pass reject reason to template
        })
    
    return redirect("login_view")  # Redirect to login if not a user

def issue_vehicle_pass(request):
    if request.session.get("role") == "user":
        if request.method == "POST":
            state_code = request.POST.get("state_code", "").upper()
            city_code = request.POST.get("city_code", "")
            series = request.POST.get("series", "").upper()
            digits = request.POST.get("digits", "")

            vehicle_number = state_code + city_code + series + digits
            vehicle_type = request.POST.get("vehicle_type", "").strip()

            # ✅ Allow insert if vehicle_number is blank
            if vehicle_number and vehicle_type != "E-Vehicle" and VehiclePass.objects.filter(vehicle_number=vehicle_number).exists():
                messages.error(request, f"🚨 આ વાહન નંબર ({vehicle_number}) માટે પહેલેથી જ અરજી થઈ ચૂકી છે!")
                return redirect("issue_vehicle_pass")

            form = VehiclePassForm(request.POST, request.FILES)
            if form.is_valid():
                vehicle_pass = form.save(commit=False)
                vehicle_pass.vehicle_number = vehicle_number if vehicle_number else None  # ✅ Allow blank vehicle_number
                vehicle_pass.vehicle_type = vehicle_type
                vehicle_pass.mobile_no = request.POST.get("mobile_no", "")

                # ✅ Store uploaded files
                vehicle_pass.aadhaar_front = request.FILES.get("aadhaar_front")
                vehicle_pass.aadhaar_back = request.FILES.get("aadhaar_back")
                vehicle_pass.rc_book = request.FILES.get("rc_book")
                vehicle_pass.license_photo = request.FILES.get("license_photo")

                # ✅ Store travel reason
                vehicle_pass.travel_reason = request.POST.get("travel_reason", "").strip()
                vehicle_pass.other_reason = request.POST.get("other_reason", "").strip()
                vehicle_pass.extra_name = request.POST.get("extra_name", "").strip()
                vehicle_pass.extra_place = request.POST.get("extra_place", "").strip()

                if vehicle_pass.travel_reason == "અન્ય" and not vehicle_pass.other_reason:
                    messages.error(request, "❌ જો તમે 'અન્ય' પસંદ કરો છે, તો કૃપા કરીને કારણ દાખલ કરો!")
                    return redirect("issue_vehicle_pass")

                # ✅ Save record
                vehicle_pass.status = "pending"
                vehicle_pass.applied_at = timezone.now()
                vehicle_pass.save()

                messages.success(request, f"✅ વાહન પાસ પર સફળતાપૂર્વક સબમિટ થઈ ગયું છે!")
                return redirect("issue_vehicle_pass")

            else:
                print(form.errors)
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
        selected_date = request.GET.get("approved_date", "").strip()
        pass_type_filter = request.GET.get("pass_type", "").strip()  # ✅ Get filter type from URL

        # Fetch all records from both tables
        vehicle_passes = VehiclePass.objects.all().order_by('-id')
        gov_vehicle_passes = GovVehiclePass.objects.all().order_by('-id')

        # Apply filtering based on pass_type
        if pass_type_filter == "private":
            passes = vehicle_passes
        elif pass_type_filter == "government":
            passes = gov_vehicle_passes
        else:
            # If no filter is applied, show both types
            passes = sorted(
                chain(vehicle_passes, gov_vehicle_passes), 
                key=lambda obj: obj.id, 
                reverse=True
            )

        total_requests = len(passes)
        all_requests = len(list(chain(vehicle_passes, gov_vehicle_passes)))

        # ✅ Apply date filtering if a date is selected
        if selected_date:
            try:
                selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
                passes = [p for p in passes if p.approved_date == selected_date]
            except ValueError:
                selected_date = ""

        # Get user details for approval tracking
        users = {user.id: user for user in User.objects.all()}

        return render(
            request, 
            "admin_vehicle_passes.html", 
            {
                "passes": passes,
                "total_requests": len(passes),
                "all_requests": all_requests,
                "selected_date": selected_date,
                "users": users,
                "pass_type_filter": pass_type_filter  # ✅ Pass the selected filter to the template
            }
        )

    return redirect(login_view)

def approved_gov(request):
    if request.session.get("role") == "user1":
        selected_date = request.GET.get("approved_date", "").strip()
        
        vehicle = GovVehiclePass.objects.all().order_by('-id')
        vehicle_passes = GovVehiclePass.objects.filter(status="approved")

        if selected_date:
            try:
                selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
                vehicle_passes = vehicle_passes.filter(approved_date=selected_date)
            except ValueError:
                selected_date = ""

        for pass_obj in vehicle_passes:
            if pass_obj.approved_by:
                user = User.objects.filter(id=pass_obj.approved_by).first()
                # pass_obj.approved_by_name = user.name if user else "Unknown"

        total_requests = len(vehicle_passes)
        tot_requests = len(vehicle)

        # ✅ Generate PDFs and ZIP file
        if request.GET.get("download_zip") == "1":
            if vehicle_passes.exists():
                return generate_zip(vehicle_passes)
            else:
                return redirect(request.path)  # Redirect if no records found

        return render(
            request,
            "approved_gov.html",
            {
                "passes": vehicle_passes,
                "total_requests": total_requests,
                "tot_requests": tot_requests,
                "passes1": vehicle,
                "selected_date": selected_date,
            },
        )

    return redirect(login_view)

def generate_zip(vehicle_passes):
    zip_filename = os.path.join(settings.MEDIA_ROOT, "vehicle-pass", "approved_passes.zip")
    os.makedirs(os.path.dirname(zip_filename), exist_ok=True)

    with zipfile.ZipFile(zip_filename, "w") as zipf:
        for pass_obj in vehicle_passes:
            pdf_path = generate_gov_pass_pdf(pass_obj,position="top")  # Generate and get PDF path
            if pdf_path:
                zipf.write(pdf_path, os.path.basename(pdf_path))

    with open(zip_filename, "rb") as zip_file:
        response = HttpResponse(zip_file.read(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="approved_passes.zip"'
        return response

def generate_gov_pass_pdf(pass_obj, position="top"):
    # ✅ Generate A5 Landscape Pass Image
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
    font_title = load_font("NotoSansGujarati-Bold.ttf", 90)
    font_main_head = load_font("NotoSansGujarati-Bold.ttf", 120)
    font_normal = load_font("NotoSansGujarati-Regular.ttf", 50)
    font_bold = load_font("NotoSansGujarati-Bold.ttf", 50)

    # ✅ Header Section
    draw.text((400, 80), "જૂનાગઢ પોલીસ - મહાશિવરાત્રી મેળો ૨૦૨૫", fill="black", font=font_main_head)
    draw.line([(100, 260), (2380, 260)], fill="black", width=6)

    formatted_date = pass_obj.approved_date.strftime("%d-%m-%Y")

    draw.text((1900, 280), f"પાસ નંબર: {pass_obj.pass_no}/2025", fill="black", font=font_bold)
    draw.text((1900, 380), f"ઈશ્યુ તારીખ: {formatted_date}", fill="black", font=font_bold)

    # ✅ Police Logo
    logo_path = os.path.join(settings.MEDIA_ROOT, "junagadh_police.png")
    if os.path.exists(logo_path):
        police_logo = Image.open(logo_path).convert("RGBA")
        police_logo = police_logo.resize((230, 230))
        img.paste(police_logo, (100, 20), police_logo)

    # ✅ QR Code Generation
    qr_data = f"""
    નામ: {pass_obj.name}
    મોબાઇલ: {pass_obj.mobile_no}
    વાહન નંબર: {pass_obj.vehicle_number}
    વાહન પ્રકાર: {pass_obj.vehicle_type}
    શરુઆત તારીખ: {pass_obj.start_date}
    અંતિમ તારીખ: {pass_obj.end_date}
    """
    
    qr = qrcode.QRCode(
        version=5, 
        error_correction=qrcode.constants.ERROR_CORRECT_H,  
        box_size=10,
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
        center_img = center_img.resize((int(qr_size // 3), int(qr_size // 3)))  

        qr_x = (qr_img.size[0] - center_img.size[0]) // 2
        qr_y = (qr_img.size[1] - center_img.size[1]) // 2
        qr_img.paste(center_img, (qr_x, qr_y), center_img)

    qr_resized = qr_img.resize((500, 500))
    img.paste(qr_resized, (1000, 1050))  

    def draw_dotted_line(draw, start_x, start_y, end_x, dot_spacing=20, dot_length=12):
        x = start_x
        while x < end_x:
            draw.line([(x, start_y), (x + dot_length, start_y)], fill="black", width=3)
            x += dot_spacing  

    # ✅ Pass Title
    draw.text((850, 280), "વાહન પ્રવેશ પરવાનગી", fill="black", font=font_title)

    # ✅ Save Image
    formatted_date_start = pass_obj.start_date.strftime("%d-%m-%Y") if pass_obj.start_date else "N/A"
    formatted_date_end = pass_obj.end_date.strftime("%d-%m-%Y") if pass_obj.end_date else "N/A"


    if pass_obj.extra_name:
        office_label = f"સરકારી કચેરીનું નામ:"
        office_value = pass_obj.extra_name
    elif pass_obj.other_reason:
        office_label = f"સરકારી કચેરીનું નામ:"
        office_value = pass_obj.other_reason
    else:
        office_label = ""
        office_value = ""
    # ✅ Vehicle Entry Details with Dotted Lines
    fields = [
        ("તારીખ:", formatted_date_start, 100, 500),
        ("થી", "", 1100, 500),
        ("તારીખ:", formatted_date_end, 1500, 500),
        ("વાહન નંબર:", pass_obj.vehicle_number, 100, 650),
        ("વાહન પ્રકાર:", pass_obj.vehicle_type, 1500, 650),
        ("નામ:", pass_obj.name, 100, 800),
        ("મોબાઇલ નંબર:", pass_obj.mobile_no, 1500, 800),
        ("પ્રવાસનું કારણ:", pass_obj.travel_reason, 100, 950),
        
    ]

    if office_label:
        fields.append((office_label, office_value, 1500, 950))

    for label, value, x, y in fields:
        draw.text((x, y), label, fill="black", font=font_bold)  # Bold Label
        draw.text((x + 400, y), f"{value}", fill="black", font=font_normal)  # Normal Value
        draw_dotted_line(draw, x, y + 60, x + 1900)  # Dotted Line

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
    image_path = os.path.join(vehicle_pass_folder, f'{pass_obj.pass_no}.png')
    img.save(image_path)

    # ✅ Ask user for position choice (frontend should send this choice in request)
    

    # ✅ Create A4 Portrait PDF and place A5 pass image inside it
    pdf_path = os.path.join(vehicle_pass_folder, f"{pass_obj.pass_no}.pdf")
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

    return pdf_path  # ✅ Return the PDF path

def approved_private(request):
    if request.session.get("role") == "user":
        selected_date = request.GET.get("approved_date", "").strip()
        
        vehicle = VehiclePass.objects.all() .order_by('-id')
        # ✅ Fetch only Approved Passes, Filter by Date if Selected
        vehicle_passes = VehiclePass.objects.filter(status="approved")

        

        if selected_date:
            try:
                selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
                vehicle_passes = vehicle_passes.filter(approved_date=selected_date)
            except ValueError:
                selected_date = ""

        # ✅ Debugging Statement (Check if Data is Fetched)
        print("Filtered Vehicle Passes:", vehicle_passes)  # 🔍 Debug Output
        
        for pass_obj in vehicle_passes:
            if pass_obj.approved_by:
                user = User.objects.filter(id=pass_obj.approved_by).first()
                # pass_obj.approved_by_name = user.name if user else "Unknown"

        total_requests = len(vehicle_passes)
        tot_requests = len(vehicle)

        if request.GET.get("download_zip") == "1":
            return generate_zip1(vehicle_passes)

        return render(
            request,
            "approved_private.html",
            {
                "passes": vehicle_passes,
                "total_requests": total_requests,
                "tot_requests": tot_requests,
                "passes1": vehicle,
                "selected_date": selected_date,  # Pass selected date to template
            },
        )

    return redirect(login_view)


def generate_zip1(vehicle_passes):
    zip_filename = os.path.join(settings.MEDIA_ROOT, "vehicle-pass", "approved_passes.zip")
    os.makedirs(os.path.dirname(zip_filename), exist_ok=True)

    with zipfile.ZipFile(zip_filename, "w") as zipf:
        for pass_obj in vehicle_passes:
            pdf_path = generate_gov_pass_pdf1(pass_obj,position="top")  # Generate and get PDF path
            if pdf_path:
                zipf.write(pdf_path, os.path.basename(pdf_path))

    with open(zip_filename, "rb") as zip_file:
        response = HttpResponse(zip_file.read(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="approved_passes.zip"'
        return response

def generate_gov_pass_pdf1(pass_obj, position="top"):
    # ✅ Generate A5 Landscape Pass Image
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
    font_title = load_font("NotoSansGujarati-Bold.ttf", 90)
    font_main_head = load_font("NotoSansGujarati-Bold.ttf", 120)
    font_normal = load_font("NotoSansGujarati-Regular.ttf", 50)
    font_bold = load_font("NotoSansGujarati-Bold.ttf", 50)

    # ✅ Header Section
    draw.text((400, 80), "જૂનાગઢ પોલીસ - મહાશિવરાત્રી મેળો ૨૦૨૫", fill="black", font=font_main_head)
    draw.line([(100, 260), (2380, 260)], fill="black", width=6)

    formatted_date = pass_obj.approved_date.strftime("%d-%m-%Y")

    draw.text((1900, 280), f"પાસ નંબર: {pass_obj.pass_no}/2025", fill="black", font=font_bold)
    draw.text((1900, 380), f"ઈશ્યુ તારીખ: {formatted_date}", fill="black", font=font_bold)

    # ✅ Police Logo
    logo_path = os.path.join(settings.MEDIA_ROOT, "junagadh_police.png")
    if os.path.exists(logo_path):
        police_logo = Image.open(logo_path).convert("RGBA")
        police_logo = police_logo.resize((230, 230))
        img.paste(police_logo, (100, 20), police_logo)

    # ✅ QR Code Generation
    qr_data = f"""
    નામ: {pass_obj.name}
    મોબાઇલ: {pass_obj.mobile_no}
    વાહન નંબર: {pass_obj.vehicle_number}
    વાહન પ્રકાર: {pass_obj.vehicle_type}
    શરુઆત તારીખ: {pass_obj.start_date}
    અંતિમ તારીખ: {pass_obj.end_date}
    """
    
    qr = qrcode.QRCode(
        version=5, 
        error_correction=qrcode.constants.ERROR_CORRECT_H,  
        box_size=10,
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
        center_img = center_img.resize((int(qr_size // 3), int(qr_size // 3)))  

        qr_x = (qr_img.size[0] - center_img.size[0]) // 2
        qr_y = (qr_img.size[1] - center_img.size[1]) // 2
        qr_img.paste(center_img, (qr_x, qr_y), center_img)

    qr_resized = qr_img.resize((500, 500))
    img.paste(qr_resized, (1000, 1050))  

    def draw_dotted_line(draw, start_x, start_y, end_x, dot_spacing=20, dot_length=12):
        x = start_x
        while x < end_x:
            draw.line([(x, start_y), (x + dot_length, start_y)], fill="black", width=3)
            x += dot_spacing  

    # ✅ Pass Title
    draw.text((850, 280), "વાહન પ્રવેશ પરવાનગી", fill="black", font=font_title)

    # ✅ Save Image
    formatted_date_start = pass_obj.start_date.strftime("%d-%m-%Y") if pass_obj.start_date else "N/A"
    formatted_date_end = pass_obj.end_date.strftime("%d-%m-%Y") if pass_obj.end_date else "N/A"


    if pass_obj.extra_name:
        office_label = f"{pass_obj.travel_reason}નું નામ:"
        office_value = pass_obj.extra_name
    elif pass_obj.other_reason:
        office_label = f"{pass_obj.travel_reason} વિગત:"
        office_value = pass_obj.other_reason
    else:
        office_label = ""
        office_value = ""
    # ✅ Vehicle Entry Details with Dotted Lines
    fields = [
        ("તારીખ:", formatted_date_start, 100, 500),
        ("થી", "", 1100, 500),
        ("તારીખ:", formatted_date_end, 1500, 500),
        ("વાહન નંબર:", pass_obj.vehicle_number, 100, 650),
        ("વાહન પ્રકાર:", pass_obj.vehicle_type, 1500, 650),
        ("નામ:", pass_obj.name, 100, 800),
        ("મોબાઇલ નંબર:", pass_obj.mobile_no, 1500, 800),
        ("પ્રવાસનું કારણ:", pass_obj.travel_reason, 100, 950),
        
    ]

    if office_label:
        fields.append((office_label, office_value, 1500, 950))

    for label, value, x, y in fields:
        draw.text((x, y), label, fill="black", font=font_bold)  # Bold Label
        draw.text((x + 500, y), f"{value}", fill="black", font=font_normal)  # Normal Value
        draw_dotted_line(draw, x, y + 60, x + 1900)  # Dotted Line

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
    image_path = os.path.join(vehicle_pass_folder, f'{pass_obj.pass_no}.png')
    img.save(image_path)

    # ✅ Ask user for position choice (frontend should send this choice in request)
    

    # ✅ Create A4 Portrait PDF and place A5 pass image inside it
    pdf_path = os.path.join(vehicle_pass_folder, f"{pass_obj.pass_no}.pdf")
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

    return pdf_path  # ✅ Return the PDF path


def export_vehicle_passes(request):
    # ✅ Create a new Excel workbook and sheet
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Vehicle Passes"

    # ✅ Add Headers (Gujarati & English Supported)
    headers = ["Pass No", "Vehicle Number", "Applicant Name", 
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
        

        # 🔹 Append Data to Excel
        sheet.append([
            p.pass_no, p.vehicle_number, p.name, p.mobile_no, p.vehicle_type, 
            p.travel_reason, p.extra_name, p.extra_place, 
            p.start_date, p.end_date, 
            p.applied_at.strftime("%d-%m-%Y"), 
            p.status, 
            p.approved_date if p.approved_date else "", 
            p.approved_by_name,  # ✅ Show Name Instead of ID
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
    headers = ["Pass No.", "Vehicle Number", "Applicant Name", 
               "Mobile", "Vehicle Type", "Reason", 
               "Extra Name", 
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
        # p.approved_by_name

        # 🔹 Append Data to Excel
        sheet.append([
            p.pass_no, p.vehicle_number, p.name, p.mobile_no, p.vehicle_type, 
            p.travel_reason, p.extra_name, 
            p.start_date, p.end_date, 
            p.applied_at.strftime("%d-%m-%Y"), 
            p.status, 
            p.approved_date if p.approved_date else "", 
            p.approved_by_name,  # ✅ Show Name Instead of ID
            p.reject_reason if p.status == "rejected" else ""
        ])

    # ✅ Set Response Headers for Excel Download
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="vehicle_passes.xlsx"'
    
    # ✅ Save the workbook to response
    workbook.save(response)
    return response

def update_gov_pass_status(request, pass_id, status):
    admin_id = request.session.get("user_id")  # Get admin ID from session
    is_admin = request.session.get("is_admin", False)  # Ensure this exists in the session

    if status not in ["approved", "rejected"]:
        return HttpResponse("❌ Invalid Status!", status=400)

    # ✅ Fetch Government Vehicle Pass
    vehicle_pass = get_object_or_404(GovVehiclePass, id=pass_id)

    print(f"🚀 DEBUG: Gov VehiclePass Found - ID: {vehicle_pass.id}, Current Status: {vehicle_pass.status}")

    # 🔄 **Admins should always be redirected to `admin_vehicle_passes`**
    redirect_url = "admin_vehicle_passes" if is_admin else "approved_gov"

    # ✅ Handle Rejection with Reason
    if status == "rejected":
        if request.method == "POST":
            reject_reason = request.POST.get("reject_reason", "").strip()
            if not reject_reason:
                messages.error(request, "❌ Please provide a reason for rejection!")
                return redirect(redirect_url)

            print(f"🛑 REJECTING GOV PASS: {vehicle_pass.id} by Admin {admin_id} with Reason: {reject_reason}")

            vehicle_pass.status = "rejected"
            vehicle_pass.reject_reason = reject_reason
            vehicle_pass.approved_by = admin_id

            if vehicle_pass.pass_no:
                print(f"⚠️ Removing pass_no: {vehicle_pass.pass_no} for rejected pass ID: {vehicle_pass.id}")
                vehicle_pass.pass_no = None  # Remove the pass number
            vehicle_pass.save()

            print(f"✅ REJECTED GOV PASS: {vehicle_pass.id}, New Status: {vehicle_pass.status}")

            messages.success(request, "❌ Government Vehicle Pass Rejected Successfully!")
            return redirect(redirect_url)

        messages.error(request, "❌ Invalid request method for rejection!")
        return redirect(redirect_url)

    # ✅ Handle Approval
    if status == "approved":
        print(f"✔️ APPROVING GOV PASS: {vehicle_pass.id} by Admin {admin_id}")

        vehicle_pass.status = "approved"
        vehicle_pass.reject_reason = ""
        vehicle_pass.approved_by = admin_id
        vehicle_pass.approved_date = now().date()

        if not vehicle_pass.pass_no:
            vehicle_pass.pass_no = vehicle_pass.generate_pass_no()

        vehicle_pass.save()

        print(f"✅ APPROVED GOV PASS: {vehicle_pass.id}, New Status: {vehicle_pass.status}")
        messages.success(request, "✅ Government Vehicle Pass Approved Successfully!")

    return redirect(redirect_url)

# ✅ Function to Update Private Vehicle Pass Status
def update_private_pass_status(request, pass_id, status):
    admin_id = request.session.get("user_id")  # Get admin ID from session
    is_admin = request.session.get("is_admin", False)  # Ensure this exists in the session

    if status not in ["approved", "rejected"]:
        return HttpResponse("❌ Invalid Status!", status=400)

    # ✅ Fetch Private Vehicle Pass
    vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)

    print(f"🚀 DEBUG: Private VehiclePass Found - ID: {vehicle_pass.id}, Current Status: {vehicle_pass.status}")

    # 🔄 **Admins should always be redirected to `admin_vehicle_passes`**
    redirect_url = "admin_vehicle_passes" if is_admin else "approved_private"

    # ✅ Handle Rejection with Reason
    if status == "rejected":
        if request.method == "POST":
            reject_reason = request.POST.get("reject_reason", "").strip()
            if not reject_reason:
                messages.error(request, "❌ Please provide a reason for rejection!")
                return redirect(redirect_url)

            print(f"🛑 REJECTING PRIVATE PASS: {vehicle_pass.id} by Admin {admin_id} with Reason: {reject_reason}")

            vehicle_pass.status = "rejected"
            vehicle_pass.reject_reason = reject_reason
            vehicle_pass.approved_by = admin_id

            if vehicle_pass.pass_no:
                print(f"⚠️ Removing pass_no: {vehicle_pass.pass_no} for rejected pass ID: {vehicle_pass.id}")
                vehicle_pass.pass_no = None  # Remove the pass number
            vehicle_pass.save()

            print(f"✅ REJECTED PRIVATE PASS: {vehicle_pass.id}, New Status: {vehicle_pass.status}")

            messages.success(request, "❌ Private Vehicle Pass Rejected Successfully!")
            return redirect(redirect_url)

        messages.error(request, "❌ Invalid request method for rejection!")
        return redirect(redirect_url)

    # ✅ Handle Approval
    if status == "approved":
        print(f"✔️ APPROVING PRIVATE PASS: {vehicle_pass.id} by Admin {admin_id}")

        vehicle_pass.status = "approved"
        vehicle_pass.reject_reason = ""
        vehicle_pass.approved_by = admin_id
        vehicle_pass.approved_date = now().date()

        if not vehicle_pass.pass_no:
            vehicle_pass.pass_no = vehicle_pass.generate_pass_no()

        vehicle_pass.save()

        print(f"✅ APPROVED PRIVATE PASS: {vehicle_pass.id}, New Status: {vehicle_pass.status}")
        messages.success(request, "✅ Private Vehicle Pass Approved Successfully!")

    return redirect(redirect_url)



def admin_update_pass_status(request, pass_id, status):
    """Handles approval/rejection by admins only."""
    admin_id = request.session.get("user_id")
    is_admin = request.session.get("is_admin", False)

    

    if status not in ["approved", "rejected"]:
        return HttpResponse("❌ Invalid Status!", status=400)

    vehicle_pass = GovVehiclePass.objects.filter(id=pass_id).first()
    if not vehicle_pass:
        vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)

    redirect_url = "admin_vehicle_passes"

    if status == "rejected":
        if request.method == "POST":
            reject_reason = request.POST.get("reject_reason", "").strip()
            if not reject_reason:
                messages.error(request, "❌ Please provide a reason for rejection!")
                return redirect(redirect_url)

            vehicle_pass.status = "rejected"
            vehicle_pass.reject_reason = reject_reason
            vehicle_pass.approved_by = admin_id
            if vehicle_pass.pass_no:
                print(f"⚠️ Removing pass_no: {vehicle_pass.pass_no} for rejected pass ID: {vehicle_pass.id}")
                vehicle_pass.pass_no = None  # Remove the pass number
            vehicle_pass.save()

            messages.success(request, "❌ Vehicle Pass Rejected Successfully!")
            return redirect(redirect_url)

        messages.error(request, "❌ Invalid request method for rejection!")
        return redirect(redirect_url)

    if status == "approved":
        vehicle_pass.status = "approved"
        vehicle_pass.reject_reason = ""
        vehicle_pass.approved_by = admin_id
        vehicle_pass.approved_date = now().date()

        if not vehicle_pass.pass_no:
            vehicle_pass.pass_no = vehicle_pass.generate_pass_no()

        vehicle_pass.save()

    messages.success(request, "✅ Vehicle Pass Approved Successfully!")
    return redirect(redirect_url)


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

    formatted_date = vehicle_pass.approved_date.strftime("%d-%m-%Y") if vehicle_pass.approved_date else "N/A"

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
    img.paste(qr_resized, (1000, 1050))  # Adjusted position

    # ✅ Function to Draw Dotted Lines
    def draw_dotted_line(draw, start_x, start_y, end_x, dot_spacing=20, dot_length=12):
        x = start_x
        while x < end_x:
            draw.line([(x, start_y), (x + dot_length, start_y)], fill="black", width=3)
            x += dot_spacing  

    # ✅ Pass Title
    draw.text((850, 280), "વાહન પ્રવેશ પરવાનગી", fill="black", font=font_title)

    formatted_date_start = vehicle_pass.start_date.strftime("%d-%m-%Y") if vehicle_pass.start_date else "N/A"
    formatted_date_end = vehicle_pass.end_date.strftime("%d-%m-%Y") if vehicle_pass.end_date else "N/A"


    if vehicle_pass.extra_name:
        office_label = f"{vehicle_pass.travel_reason}નું નામ:"
        office_value = vehicle_pass.extra_name
    elif vehicle_pass.other_reason:
        office_label = f"{vehicle_pass.travel_reason} વિગત:"
        office_value = vehicle_pass.other_reason
    else:
        office_label = ""
        office_value = ""
    # ✅ Vehicle Entry Details with Dotted Lines
    fields = [
        ("તારીખ:", formatted_date_start, 100, 500),
        ("થી", "", 1100, 500),
        ("તારીખ:", formatted_date_end, 1500, 500),
        ("વાહન નંબર:", vehicle_pass.vehicle_number, 100, 650),
        ("વાહન પ્રકાર:", vehicle_pass.vehicle_type, 1500, 650),
        ("નામ:", vehicle_pass.name, 100, 800),
        ("મોબાઇલ નંબર:", vehicle_pass.mobile_no, 1500, 800),
        ("પ્રવાસનું કારણ:", vehicle_pass.travel_reason, 100, 950),
        
    ]

    if office_label:
        fields.append((office_label, office_value, 1500, 950))

    for label, value, x, y in fields:
        draw.text((x, y), label, fill="black", font=font_bold)  # Bold Label
        draw.text((x + 450, y), f"{value}", fill="black", font=font_normal)  # Normal Value
        draw_dotted_line(draw, x, y + 60, x + 1900)  # Dotted Line

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
    image_path = os.path.join(vehicle_pass_folder, f'{vehicle_pass.pass_no}.png')
    img.save(image_path)

    # ✅ Ask user for position choice (frontend should send this choice in request)
    position = request.GET.get("position", "top")  # Default to "top" if not provided

    # ✅ Create A4 Portrait PDF and place A5 pass image inside it
    pdf_path = os.path.join(vehicle_pass_folder, f"{vehicle_pass.pass_no}.pdf")
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
        response["Content-Disposition"] = f'attachment; filename="{vehicle_pass.pass_no}.pdf"'
        return response
    
    

# def download_approved_passes(request):
#     selected_date = request.GET.get("approved_date", "").strip()

#     if not selected_date:
#         return HttpResponse("❌ Please select an approval date.", status=400)

#     print(f"📅 Received Date: {selected_date}")  # Debugging step

#     try:
#         # ✅ Try parsing in both common formats (YYYY-MM-DD or DD-MM-YYYY)
#         for fmt in ["%Y-%m-%d", "%d-%m-%Y"]:
#             try:
#                 selected_date = datetime.strptime(selected_date, fmt).date()
#                 print(f"✅ Parsed Date: {selected_date}")  # Debugging step
#                 break
#             except ValueError:
#                 continue
#         else:
#             return HttpResponse("❌ Invalid date format. Use YYYY-MM-DD or DD-MM-YYYY.", status=400)

#     except ValueError:
#         return HttpResponse("❌ Invalid date format.", status=400)

#     # 🔹 Fetch Only Approved Passes for Selected Date
#     passes = VehiclePass.objects.filter(status="approved", approved_date=selected_date)


#     if not passes.exists():
#         return HttpResponse("❌ No approved passes found for the selected date.", status=404)

#     # ✅ Ensure "generate_pass_pdf" folder exists
#     generate_pdf_folder = os.path.join(settings.MEDIA_ROOT, "generate_pass_pdf")
#     if not os.path.exists(generate_pdf_folder):
#         os.makedirs(generate_pdf_folder)  # 🔥 Create the folder if it doesn't exist

#     # 🔥 Step 1: Generate PDFs for Each Approved Pass
#     for pass_obj in passes:
#         pass_pdf_path = os.path.join(generate_pdf_folder, f"{pass_obj.vehicle_number}.pdf")
        
#         if not os.path.exists(pass_pdf_path):  # 🔹 Generate only if not already created
#             generate_pass_image(pass_obj, pass_pdf_path)
#             print(f"📄 Generated Pass PDF: {pass_pdf_path}")  # Debugging step

#     # ✅ Create ZIP File Path
#     zip_filename = f"approved_passes_{selected_date}.zip"
#     zip_path = os.path.join(settings.MEDIA_ROOT, zip_filename)  # ✅ Store ZIP in `media/`

#     # 🔥 Step 2: Create ZIP File & Add Only PDF Passes
#     with zipfile.ZipFile(zip_path, "w") as zipf:
#         added_files = 0  # Counter to check if any files are added
        
#         for pass_obj in passes:
#             pass_pdf_path = os.path.join(generate_pdf_folder, f"{pass_obj.vehicle_number}.pdf")
            
#             if os.path.exists(pass_pdf_path):  # ✅ Ensure the pass PDF exists
#                 zipf.write(pass_pdf_path, os.path.basename(pass_pdf_path))
#                 print(f"✅ Added to ZIP: {pass_pdf_path}")  # Debugging step
#                 added_files += 1  

#     if added_files == 0:
#         return HttpResponse("❌ No pass PDFs found for the selected date.", status=404)

#     # 📥 Step 3: Serve ZIP File for Download
#     with open(zip_path, "rb") as zip_file:
#         response = HttpResponse(zip_file.read(), content_type="application/zip")
#         response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
#         return response

def generate_gov_pass_image(request, pass_id):
    # ✅ Get the pass record
    vehicle_pass = get_object_or_404(GovVehiclePass, id=pass_id)

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
    img.paste(qr_resized, (1000, 1050))  # Adjusted position

    # ✅ Function to Draw Dotted Lines
    def draw_dotted_line(draw, start_x, start_y, end_x, dot_spacing=20, dot_length=12):
        x = start_x
        while x < end_x:
            draw.line([(x, start_y), (x + dot_length, start_y)], fill="black", width=3)
            x += dot_spacing  

    # ✅ Pass Title
    draw.text((850, 280), "વાહન પ્રવેશ પરવાનગી", fill="black", font=font_title)

    formatted_date_start = vehicle_pass.start_date.strftime("%d-%m-%Y") if vehicle_pass.start_date else "N/A"
    formatted_date_end = vehicle_pass.end_date.strftime("%d-%m-%Y") if vehicle_pass.end_date else "N/A"

    # ✅ Vehicle Entry Details with Dotted Lines
    fields = [
        ("તારીખ:", formatted_date_start, 100, 500),
        ("થી", "", 1100, 500),
        ("તારીખ:", formatted_date_end, 1500, 500),
        ("વાહન નંબર:", vehicle_pass.vehicle_number, 100, 650),
        ("વાહન પ્રકાર:", vehicle_pass.vehicle_type, 1500, 650),
        ("નામ:", vehicle_pass.name, 100, 800),
        ("મોબાઇલ નંબર:", vehicle_pass.mobile_no, 1500, 800),
        ("પ્રવાસનું કારણ:", vehicle_pass.travel_reason, 100, 950),
        (f"કચેરીનું નામ:", vehicle_pass.extra_name, 1500, 950),
    ]

    for label, value, x, y in fields:
        draw.text((x, y), label, fill="black", font=font_bold)  # Bold Label
        draw.text((x + 340, y), f"{value}", fill="black", font=font_normal)  # Normal Value
        draw_dotted_line(draw, x, y + 60, x + 1900)  # Dotted Line

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
    image_path = os.path.join(vehicle_pass_folder, f'{vehicle_pass.pass_no}.png')
    img.save(image_path)

    # ✅ Ask user for position choice (frontend should send this choice in request)
    position = request.GET.get("position", "top")  # Default to "top" if not provided

    # ✅ Create A4 Portrait PDF and place A5 pass image inside it
    pdf_path = os.path.join(vehicle_pass_folder, f"{vehicle_pass.pass_no}.pdf")
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
        response["Content-Disposition"] = f'attachment; filename="{vehicle_pass.pass_no}.pdf"'
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

def download_gov_images(request, pass_id):
    # ✅ Get the vehicle pass record
    vehicle_pass = get_object_or_404(GovVehiclePass, id=pass_id)

    # ✅ Get all images associated with the pass
    image_fields = ['photo1']
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

def admin_download_pass_images(request, pass_id):
    """Download images for both GovVehiclePass & VehiclePass."""
    
    # ✅ Try finding the pass in both tables
    vehicle_pass = GovVehiclePass.objects.filter(id=pass_id).first()
    image_fields = ["photo1"]  # ✅ Default image fields for GovVehiclePass

    if not vehicle_pass:
        vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)
        image_fields = ["aadhaar_front", "aadhaar_back", "rc_book", "license_photo"]  # ✅ Private vehicle fields

    # ✅ Get existing image paths
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
    
def update_vehicle_pass(request, pass_id):
    if request.session.get("role") == "user":
        vehicle_pass = get_object_or_404(VehiclePass, id=pass_id)
        
        if request.method == "POST":
            form = VehiclePassUpdateForm(request.POST, instance=vehicle_pass)
            if form.is_valid():
                form.save()
                return redirect("approved_private")  # Redirect to list page

        else:
            form = VehiclePassUpdateForm(instance=vehicle_pass)

        return render(request, "update_vehicle_pass.html", {"form": form, "vehicle_pass": vehicle_pass})
    return redirect(login_view)

def update_gov_vehicle_pass(request, pass_id):
    if request.session.get("role") == "user1":
        vehicle_pass = get_object_or_404(GovVehiclePass, id=pass_id)
        
        if request.method == "POST":
            form = GovVehiclePassUpdateForm(request.POST, instance=vehicle_pass)
            if form.is_valid():
                form.save()
                return redirect("approved_gov")  # Redirect to list page

        else:
            form = GovVehiclePassUpdateForm(instance=vehicle_pass)

        return render(request, "update_gov_vehicle_pass.html", {"form": form, "vehicle_pass": vehicle_pass})
    return redirect(login_view)