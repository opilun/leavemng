import datetime

from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Add your custom fields here
    position = models.CharField(max_length=100, default="")
    mobile = models.CharField(max_length=15, default="")

    sick_leave_total = models.IntegerField(default=30)
    sick_leave_used = models.IntegerField(default=0)
    sick_leave_remaining = models.IntegerField(default=30)

    absence_leave_total = models.IntegerField(default=30)
    absence_leave_used = models.IntegerField(default=0)
    absence_leave_remaining = models.IntegerField(default=30)

    vacation_leave_total = models.IntegerField(default=15)
    vacation_leave_used = models.IntegerField(default=0)
    vacation_leave_remaining = models.IntegerField(default=15)


class Holiday(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.date})"


class Leave_Detail(models.Model):
    REASON_CHOICES = [
        ("ป่วย", "ป่วย"),
        ("กิจส่วนตัว", "กิจส่วนตัว"),
        ("ลาพักร้อน", "ลาพักร้อน"),
    ]
    STATUS_CHOICES = [
        ("รอดำเนินการ", "รอดำเนินการ"),
        ("อนุมัติ", "อนุมัติ"),
        ("ไม่อนุมัติ", "ไม่อนุมัติ"),
    ]
    name = models.CharField(max_length=150)
    submit_date = models.DateField(default=datetime.date.today)
    leave_date_from = models.DateField()
    leave_date_to = models.DateField()
    leave_days_count = models.IntegerField(default=0)

    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    document = models.FileField(upload_to="leave_documents/", blank=True, null=True)

    status = models.CharField(
        max_length=20, default="รอดำเนินการ", choices=STATUS_CHOICES
    )
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.leave_date_from} ({self.reason})"
