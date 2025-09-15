import datetime
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.shortcuts import redirect, render

# Delete leave view
from django.views.decorators.http import require_POST
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import Holiday, Leave_Detail, Profile

# Create your views here.


def home(request):
    # Redirect admin users to approve_leave
    if (
        request.user.is_authenticated
        and request.user.groups.filter(name="leaveAdmin").exists()
    ):
        return redirect("approve_leave")
    profile = Profile.objects.get(user=request.user)
    leave_history = Leave_Detail.objects.filter(
        name=request.user.get_full_name()
    ).order_by("-submit_date", "-id")
    return render(
        request,
        "leaveapp/home.html",
        {
            "profile": profile,
            "leave_history": leave_history,
            "is_leave_admin": request.user.groups.filter(name="leaveAdmin").exists(),
        },
    )


def approve_leave(request):
    if not request.user.groups.filter(name="leaveAdmin").exists():
        messages.error(request, "You do not have permission to access this page.")
        return redirect("home")
    # Show all records in Leave_History
    leave_history = Leave_Detail.objects.all().order_by("-submit_date", "-id")
    return render(
        request, "leaveapp/approve_leave.html", {"leave_history": leave_history}
    )


def login_page(request):
    # If user is already authenticated, redirect based on group
    if request.user.is_authenticated:
        if request.user.groups.filter(name="leaveUser").exists():
            return redirect("home")
        elif request.user.groups.filter(name="leaveAdmin").exists():
            return redirect("approve_leave")
        else:
            return redirect("login")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect based on group after login
            if user.groups.filter(name="leaveUser").exists():
                return redirect("home")
            elif user.groups.filter(name="leaveAdmin").exists():
                return redirect("approve_leave")
            else:
                return redirect("login")
        else:
            messages.error(request, "Username or password is incorrect.")
    return render(request, "accounts/login.html")


def holiday(request):
    holidays = Holiday.objects.all()
    return render(request, "leaveapp/holiday.html", {"holidays": holidays})


def change_password(request):
    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not request.user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "New password and confirmation do not match.")
        elif len(new_password) < 8:
            messages.error(request, "New password must be at least 8 characters long.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(
                request, "Password changed successfully. Please log in again."
            )
            return redirect("login")

    return render(request, "accounts/change_password.html")


def formleave(request):
    user = request.user
    # Determine admin flag and load profile if available
    is_leave_admin = (
        user.is_authenticated and user.groups.filter(name="leaveAdmin").exists()
    )
    profile = None
    if user.is_authenticated:
        try:
            profile = Profile.objects.get(user=user)
        except Profile.DoesNotExist:
            profile = None

    if request.method == "POST":
        # Use posted name if provided, otherwise default to current user's full name
        posted_name = (request.POST.get("name") or "").strip()
        name = posted_name or (
            user.get_full_name() if user.is_authenticated else user.username
        )

        submit_date = datetime.date.today()
        leave_date_from_str = request.POST.get("submit_date")
        leave_date_to_str = request.POST.get("leave_date")
        reason = request.POST.get("reason")
        document = request.FILES.get("document")
        remarks = request.POST.get("remarks")

        # Convert string dates to date objects
        try:
            leave_date_from = datetime.datetime.strptime(
                leave_date_from_str, "%Y-%m-%d"
            ).date()
            leave_date_to = datetime.datetime.strptime(
                leave_date_to_str, "%Y-%m-%d"
            ).date()
        except Exception:
            messages.error(request, "Invalid date format.")
            return render(
                request,
                "leaveapp/formleave.html",
                {"user": user, "profile": profile, "is_leave_admin": is_leave_admin},
            )

        if leave_date_to < leave_date_from:
            messages.error(request, "End date must be on or after start date.")
            return render(
                request,
                "leaveapp/formleave.html",
                {"user": user, "profile": profile, "is_leave_admin": is_leave_admin},
            )

        # Get all holidays as a set of dates
        holidays = set(Holiday.objects.values_list("date", flat=True))

        # Calculate leave days excluding weekends and holidays
        leave_days_count = 0
        current_day = leave_date_from
        while current_day <= leave_date_to:
            if current_day.weekday() not in (5, 6) and current_day not in holidays:
                leave_days_count += 1
            current_day += datetime.timedelta(days=1)

        # Check leave remaining for the selected type (if profile exists)
        if profile is not None:
            leave_remaining = None
            if reason == "ป่วย":
                leave_remaining = profile.sick_leave_remaining
            elif reason == "กิจส่วนตัว":
                leave_remaining = profile.absence_leave_remaining
            elif reason == "ลาพักร้อน":
                leave_remaining = profile.vacation_leave_remaining

            if leave_remaining is not None and leave_days_count > leave_remaining:
                messages.error(
                    request,
                    f"You cannot request more days than your remaining leave ({leave_remaining} days left).",
                )
                return render(
                    request,
                    "leaveapp/formleave.html",
                    {
                        "user": user,
                        "profile": profile,
                        "is_leave_admin": is_leave_admin,
                    },
                )

        # Create leave request
        Leave_Detail.objects.create(
            name=name,
            submit_date=submit_date,
            leave_date_from=leave_date_from,
            leave_date_to=leave_date_to,
            leave_days_count=leave_days_count,
            reason=reason,
            document=document,
            remarks=remarks,
        )
        messages.success(
            request,
            f"Leave submitted successfully! Total leave days: {leave_days_count}",
        )
        return redirect("home")

    # GET request -> render form
    return render(
        request,
        "leaveapp/formleave.html",
        {"user": user, "profile": profile, "is_leave_admin": is_leave_admin},
    )


@require_POST
def delete_leave(request, leave_id):
    user = request.user
    try:
        if user.groups.filter(name="leaveAdmin").exists():
            leave = Leave_Detail.objects.get(id=leave_id)
        else:
            leave = Leave_Detail.objects.get(id=leave_id, name=user.get_full_name())
            if leave.status in ["อนุมัติ", "ไม่อนุมัติ"]:
                messages.error(
                    request,
                    "You cannot delete this leave after it has been approved or not approved.",
                )
                return redirect("home")
        leave.delete()
        messages.success(request, "Leave record deleted successfully.")
    except Leave_Detail.DoesNotExist:
        messages.error(
            request,
            "Leave record not found or you do not have permission to delete it.",
        )
    return redirect("home")


def edit_leave(request, leave_id):
    user = request.user
    is_leave_admin = user.groups.filter(name="leaveAdmin").exists()
    try:
        if is_leave_admin:
            leave = Leave_Detail.objects.get(id=leave_id)
        else:
            leave = Leave_Detail.objects.get(id=leave_id, name=user.get_full_name())
            if leave.status in ["อนุมัติ", "ไม่อนุมัติ"]:
                messages.error(
                    request,
                    "You cannot edit this leave after it has been approved or not approved.",
                )
                return redirect("home")
    except Leave_Detail.DoesNotExist:
        messages.error(
            request, "Leave record not found or you do not have permission to edit it."
        )
        return redirect("home")

    if request.method == "POST":
        leave_date_from_str = request.POST.get("submit_date")
        leave_date_to_str = request.POST.get("leave_date")
        try:
            leave.leave_date_from = datetime.datetime.strptime(
                leave_date_from_str, "%Y-%m-%d"
            ).date()
            leave.leave_date_to = datetime.datetime.strptime(
                leave_date_to_str, "%Y-%m-%d"
            ).date()
        except Exception:
            messages.error(request, "Invalid date format.")
            try:
                current_profile = Profile.objects.get(user=user)
            except Profile.DoesNotExist:
                current_profile = None
            return render(
                request,
                "leaveapp/formleave.html",
                {
                    "user": user,
                    "profile": current_profile,
                    "leave": leave,
                    "is_leave_admin": is_leave_admin,
                },
            )
        leave.reason = request.POST.get("reason")
        old_status = leave.status
        leave.remarks = request.POST.get("remarks")
        if is_leave_admin:
            leave.status = request.POST.get("status")
        if request.FILES.get("document"):
            leave.document = request.FILES.get("document")

        holidays = set(
            [
                h if not hasattr(h, "date") else h.date()
                for h in Holiday.objects.values_list("date", flat=True)
            ]
        )
        leave_days_count = 0
        for i in range((leave.leave_date_to - leave.leave_date_from).days + 1):
            day = leave.leave_date_from + datetime.timedelta(days=i)
            if hasattr(day, "date"):
                day_only = day.date()
            else:
                day_only = day
            if (day_only not in holidays) and (day.weekday() not in (5, 6)):
                leave_days_count += 1
        leave.leave_days_count = leave_days_count

        if (
            is_leave_admin
            and old_status != leave.status
            and leave.status in ["อนุมัติ", "ไม่อนุมัติ"]
        ):
            try:
                from django.contrib.auth.models import User

                user_obj = User.objects.get(
                    first_name=leave.name.split(" ")[0],
                    last_name=" ".join(leave.name.split(" ")[1:]),
                )
                profile = Profile.objects.get(user=user_obj)
                if leave.status == "อนุมัติ":
                    if leave.reason == "ป่วย":
                        profile.sick_leave_used += leave.leave_days_count
                        profile.sick_leave_remaining = (
                            profile.sick_leave_total - profile.sick_leave_used
                        )
                    elif leave.reason == "กิจส่วนตัว":
                        profile.absence_leave_used += leave.leave_days_count
                        profile.absence_leave_remaining = (
                            profile.absence_leave_total - profile.absence_leave_used
                        )
                    elif leave.reason == "ลาพักร้อน":
                        profile.vacation_leave_used += leave.leave_days_count
                        profile.vacation_leave_remaining = (
                            profile.vacation_leave_total - profile.vacation_leave_used
                        )
                    profile.save()
            except (Profile.DoesNotExist, User.DoesNotExist):
                pass

        leave.save()
        messages.success(request, "Leave record updated successfully.")
        return redirect("home")

    profile = None
    if user.is_authenticated:
        try:
            profile = Profile.objects.get(user=user)
        except Profile.DoesNotExist:
            profile = None
    return render(
        request,
        "leaveapp/formleave.html",
        {
            "user": user,
            "profile": profile,
            "leave": leave,
            "is_leave_admin": is_leave_admin,
        },
    )


def export_leave_pdf(request, leave_id):
    leave = Leave_Detail.objects.get(id=leave_id)
    response = HttpResponse(content_type="application/pdf")
    # Get firstname, lastname, position and mobile from Profile model
    # Find Profile by matching full name to user
    from django.contrib.auth.models import User

    try:
        user = User.objects.get(
            first_name=leave.name.split(" ")[0],
            last_name=" ".join(leave.name.split(" ")[1:]),
        )
        profile = Profile.objects.get(user=user)
    except (User.DoesNotExist, Profile.DoesNotExist):
        return HttpResponse("Profile matching query does not exist", status=404)

    # Format: username_submitdate_leave_id.pdf
    username = leave.name
    submitdate = (
        leave.submit_date.strftime("%Y%m%d")
        if hasattr(leave.submit_date, "strftime")
        else str(leave.submit_date)
    )
    filename = f"{username}_{submitdate}_{leave_id}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    p = canvas.Canvas(response, pagesize=(595, 842))  # A4 size

    # Register Thai fonts
    font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "THSarabunNew.ttf")
    bold_font_path = os.path.join(
        settings.BASE_DIR, "static", "fonts", "THSarabunNew Bold.ttf"
    )
    pdfmetrics.registerFont(TTFont("THSarabunNew", font_path))
    pdfmetrics.registerFont(TTFont("THSarabunNew Bold", bold_font_path))
    p.setFont("THSarabunNew Bold", 22)

    y = 750
    p.drawCentredString(297, y, "ใบคำขอลา (Leave Request)")
    y -= 50
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(400, y, "เขียนที่ ")
    p.setFont("THSarabunNew", 18)
    p.drawString(450, y, "บริษัท")
    y -= 20
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(400, y, "วันที่ ")
    p.setFont("THSarabunNew", 18)
    p.drawString(450, y, f"{leave.submit_date.strftime('%d/%m/%Y')}")
    y -= 30
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "เรื่อง ")
    p.setFont("THSarabunNew", 18)
    p.drawString(120, y, "ขออนุมัติลาหยุด")
    y -= 20
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "เรียน ")
    p.setFont("THSarabunNew", 18)
    p.drawString(120, y, "หัวหน้าแผนก")
    y -= 30
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "ข้าพเจ้า :  ")
    p.setFont("THSarabunNew", 18)
    p.drawString(140, y, f"{profile.user.first_name} {profile.user.last_name}")
    y -= 20
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "ตำแหน่ง :  ")
    p.setFont("THSarabunNew", 18)
    p.drawString(140, y, f"{profile.position}")
    y -= 20
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "เหตุผล : ")
    p.setFont("THSarabunNew", 18)
    p.drawString(140, y, f"{leave.reason}")
    y -= 20
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "เริ่มวันที่ : ")
    p.setFont("THSarabunNew", 18)
    p.drawString(140, y, f"{leave.leave_date_from.strftime('%d/%m/%Y')}")
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(250, y, "ถึงวันที่ : ")
    p.setFont("THSarabunNew", 18)
    p.drawString(300, y, f"{leave.leave_date_to.strftime('%d/%m/%Y')}")
    y -= 20
    p.setFont("THSarabunNew", 18)
    p.drawString(80, y, "จำนวนวันลาทั้งหมด ")
    p.drawString(180, y, f"{leave.leave_days_count} วัน ")
    y -= 20
    p.drawString(80, y, f"และในระหว่างลา สามารถติดต่อข้าพเจ้าได้ที่เบอร์โทรศัพท์ {profile.mobile}")
    y -= 20
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "หมายเหตุ : ")
    p.setFont("THSarabunNew", 18)
    # Draw remarks, wrap to new lines if too long
    remarks_text = leave.remarks if leave.remarks else ""
    max_width = 400  # Adjust as needed for your layout
    lines = simpleSplit(str(remarks_text), "THSarabunNew", 18, max_width)
    for line in lines:
        p.drawString(140, y, line)
        y -= 20
    y -= 30
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "สถานะ : ")
    p.setFont("THSarabunNew", 18)
    p.drawString(130, y, f"{leave.status}")
    y -= 40
    # Draw table headers
    p.setFont("THSarabunNew", 18)
    table_y = y
    # Set font to bold for headers
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, table_y, "ประเภทการลา")
    p.drawString(220, table_y, "สิทธิ (วัน)")
    p.drawString(300, table_y, "ใช้ไป (วัน)")
    p.drawString(380, table_y, "คงเหลือ (วัน)")
    # Switch back to normal font for table rows
    p.setFont("THSarabunNew", 18)
    y -= 20

    # Draw table rows
    leave_types = [
        (
            "ลาป่วย",
            profile.sick_leave_total,
            profile.sick_leave_used,
            profile.sick_leave_remaining,
        ),
        (
            "ลากิจ",
            profile.absence_leave_total,
            profile.absence_leave_used,
            profile.absence_leave_remaining,
        ),
        (
            "ลาพักร้อน",
            profile.vacation_leave_total,
            profile.vacation_leave_used,
            profile.vacation_leave_remaining,
        ),
    ]
    for leave_type, total, used, remaining in leave_types:
        p.drawString(80, y, str(leave_type))
        p.drawString(220, y, str(total))
        p.drawString(300, y, str(used))
        p.drawString(380, y, str(remaining))
        y -= 20
    y -= 80
    p.setFont("THSarabunNew Bold", 18)
    p.drawString(80, y, "ลงชื่อ ............................................")
    p.drawString(350, y, "ลงชื่อ............................................")
    y -= 40
    p.drawString(100, y, "(                                    )")
    p.drawString(360, y, "(                                    )")
    y -= 40
    p.drawString(150, y, "ผู้อนุมัติ")
    p.drawString(410, y, "ผู้ขออนุมัติลา")

    p.showPage()
    p.save()
    return response
