from django.contrib import messages
from django.contrib.auth import authenticate, login

# from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from leaveapp.models import Profile


# @login_required(login_url="login")
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


def edit_user(request, user_id):
    user = request.user
    is_leave_admin = user.groups.filter(name="leaveAdmin").exists()
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        user.email = request.POST.get("email")
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.is_staff = bool(request.POST.get("is_staff"))
        user.is_active = bool(request.POST.get("is_active"))
        user.save()
        messages.success(request, "User updated successfully.")
        return redirect("user_management")
    return render(
        request,
        "accounts/edit_user.html",
        {"user_obj": user, "is_leave_admin": is_leave_admin},
    )


def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        user.delete()
        messages.success(request, "User deleted successfully.")
        return redirect("user_management")
    return render(request, "accounts/confirm_delete.html", {"user_obj": user})


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


# show all user from Profile model
def user_management(request):
    if not request.user.groups.filter(name="leaveAdmin").exists():
        messages.error(request, "You do not have permission to access this page.")
        return redirect("home")
    profiles = Profile.objects.all().order_by("user__first_name", "user__last_name")
    return render(
        request, "accounts/usermng.html", {"profiles": profiles, "is_leave_admin": True}
    )
