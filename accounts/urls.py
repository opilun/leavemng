from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_page, name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("edit_user/<int:user_id>/", views.edit_user, name="edit_user"),
    path("delete_user/<int:user_id>/", views.delete_user, name="delete_user"),
    path("change_password/", views.change_password, name="change_password"),
    path("user_management/", views.user_management, name="user_management"),
    path("add_user/", views.add_user, name="add_user"),
]
