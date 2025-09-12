import datetime
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.shortcuts import redirect, render

# Delete leave view
from django.views.decorators.http import require_POST
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import Holiday, Leave_Detail, Profile

# Create your views here.


def home(request):
    user = request.user
    profile = None
    leave_history = Leave_Detail.objects.none()

    if user.is_authenticated:
        try:
            profile = Profile.objects.get(user=user)
        except Profile.DoesNotExist:
            profile = None

        if user.groups.filter(name="leaveAdmin").exists():
            leave_history = Leave_Detail.objects.all().order_by("-submit_date", "-id")
        elif user.groups.filter(name="leaveUser").exists():
            leave_history = Leave_Detail.objects.filter(name=user.username).order_by(
                "-submit_date", "-id"
            )
        else:
            leave_history = Leave_Detail.objects.none()

    return render(
        request,
        "leaveapp/home.html",
        {"user": user, "profile": profile, "leave_history": leave_history},
    )


def login_page(request):
    # check if user is already authenticated then redirect to home
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Username or password is incorrect.")
    return render(request, "accounts/login.html")


def holiday(request):
    holidays = Holiday.objects.all()
    return render(request, "leaveapp/holiday.html", {"holidays": holidays})


def formleave(request):
    user = request.user
    profile = None
    is_leave_admin = (
        user.groups.filter(name="leaveAdmin").exists()
        if user.is_authenticated
        else False
    )
    if user.is_authenticated:
        try:
            profile = Profile.objects.get(user=user)
        except Profile.DoesNotExist:
            profile = None

    if request.method == "POST":
        name = request.POST.get("name")
        # Always use today for submit_date when creating
        submit_date = datetime.date.today().strftime("%Y-%m-%d")
        leave_date_from = request.POST.get("submit_date")
        leave_date_to = request.POST.get("leave_date")
        reason = request.POST.get("reason")
        document = request.FILES.get("document")

        # Convert string dates to date objects
        leave_date_from_obj = datetime.datetime.strptime(
            leave_date_from, "%Y-%m-%d"
        ).date()
        leave_date_to_obj = datetime.datetime.strptime(leave_date_to, "%Y-%m-%d").date()

        # Get all holidays as a set of dates
        holidays = set(Holiday.objects.values_list("date", flat=True))

        # Calculate leave days excluding weekends and holidays
        leave_days = [
            leave_date_from_obj + datetime.timedelta(days=i)
            for i in range((leave_date_to_obj - leave_date_from_obj).days + 1)
            if (
                (leave_date_from_obj + datetime.timedelta(days=i)) not in holidays
                and (leave_date_from_obj + datetime.timedelta(days=i)).weekday()
                not in (5, 6)  # 5=Saturday, 6=Sunday
            )
        ]
        leave_days_count = len(leave_days)

        # Check leave remaining for the selected type
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
                {"user": user, "profile": profile, "is_leave_admin": is_leave_admin},
            )

        Leave_Detail.objects.create(
            name=name,
            submit_date=submit_date,
            leave_date_from=leave_date_from,
            leave_date_to=leave_date_to,
            leave_days_count=leave_days_count,
            reason=reason,
            document=document,
            # You may want to add a field for leave_days_count in your model
        )
        messages.success(
            request,
            f"Leave submitted successfully! Total leave days: {leave_days_count}",
        )
        return redirect("home")

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
            leave = Leave_Detail.objects.get(id=leave_id, name=user.username)
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
            leave = Leave_Detail.objects.get(id=leave_id, name=user.username)
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
        # Do not update submit_date on edit
        leave.leave_date_from = request.POST.get("submit_date")
        leave.leave_date_to = request.POST.get("leave_date")
        leave.reason = request.POST.get("reason")
        old_status = leave.status
        if is_leave_admin:
            leave.status = request.POST.get("status")
        if request.FILES.get("document"):
            leave.document = request.FILES.get("document")

        # Recalculate leave_days_count
        leave_date_from_obj = datetime.datetime.strptime(
            leave.leave_date_from, "%Y-%m-%d"
        ).date()
        leave_date_to_obj = datetime.datetime.strptime(
            leave.leave_date_to, "%Y-%m-%d"
        ).date()
        holidays = set(Holiday.objects.values_list("date", flat=True))
        leave_days = [
            leave_date_from_obj + datetime.timedelta(days=i)
            for i in range((leave_date_to_obj - leave_date_from_obj).days + 1)
            if (
                (leave_date_from_obj + datetime.timedelta(days=i)) not in holidays
                and (leave_date_from_obj + datetime.timedelta(days=i)).weekday()
                not in (5, 6)
            )
        ]
        leave.leave_days_count = len(leave_days)

        # Update Profile leave counts if status changed to approved or not approved
        if (
            is_leave_admin
            and old_status != leave.status
            and leave.status in ["อนุมัติ", "ไม่อนุมัติ"]
        ):
            try:
                profile = Profile.objects.get(user__username=leave.name)
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
            except Profile.DoesNotExist:
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

    # Register Thai font
    font_path = os.path.join(settings.BASE_DIR, "static", "fonts", "THSarabunNew.ttf")
    pdfmetrics.registerFont(TTFont("THSarabunNew", font_path))
    p.setFont("THSarabunNew", 22)

    y = 800
    p.drawCentredString(297, y, "ใบคำขอลา (Leave Request)")
    y -= 50
    p.setFont("THSarabunNew", 18)
    p.drawString(80, y, f"ชื่อ: {leave.name}")
    y -= 30
    p.drawString(80, y, f"วันที่ยื่น: {leave.submit_date.strftime('%d/%m/%Y')}")
    y -= 30
    p.drawString(80, y, f"วันที่ลา: {leave.leave_date_from.strftime('%d/%m/%Y')}")
    y -= 30
    p.drawString(80, y, f"ถึงวันที่: {leave.leave_date_to.strftime('%d/%m/%Y')}")
    y -= 30
    p.drawString(80, y, f"จำนวนวันลา: {leave.leave_days_count}")
    y -= 30
    p.drawString(80, y, f"เหตุผลการลา: {leave.reason}")
    y -= 30
    p.drawString(80, y, f"สถานะ: {leave.status}")

    y -= 60
    p.drawString(350, y, "ลงชื่อ.............................................")
    y -= 30
    p.drawString(400, y, "ผู้ขออนุมัติลา")

    p.showPage()
    p.save()
    return response
