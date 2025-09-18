from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("holidays/", views.holiday, name="holidays"),
    path("formleave/", views.formleave, name="formleave"),
    path("delete_leave/<int:leave_id>/", views.delete_leave, name="delete_leave"),
    path("edit_leave/<int:leave_id>/", views.edit_leave, name="edit_leave"),
    path("leave/<int:leave_id>/pdf/", views.export_leave_pdf, name="export_leave_pdf"),
    path("approve_leave/", views.approve_leave, name="approve_leave"),
    path("approve_form/<int:leave_id>/", views.approve_form, name="approve_form"),
]
