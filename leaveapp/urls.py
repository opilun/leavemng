from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_page, name="login"),
    path("home/", views.home, name="home"),
    path("holidays/", views.holiday, name="holidays"),
    path("formleave/", views.formleave, name="formleave"),
    path("delete_leave/<int:leave_id>/", views.delete_leave, name="delete_leave"),
    path("edit_leave/<int:leave_id>/", views.edit_leave, name="edit_leave"),
    path("leave/<int:leave_id>/pdf/", views.export_leave_pdf, name="export_leave_pdf"),
    path("change_password/", views.change_password, name="change_password"),
    path("approve_leave/", views.approve_leave, name="approve_leave"),
]
