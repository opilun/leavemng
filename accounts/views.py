from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render

from leaveapp.models import Profile


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


@login_required(login_url="login")
def edit_user(request, user_id):
    current_user = request.user
    is_leave_admin = current_user.groups.filter(name="leaveAdmin").exists()
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(Profile, user=user)
    user_groups = list(user.groups.values_list("name", flat=True))

    if request.method == "POST":
        # Update User fields
        user.email = request.POST.get("email")
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.is_active = True if request.POST.get("is_active") == "on" else False
        user.save()

        # Update Profile fields
        profile.position = request.POST.get("position")
        profile.mobile = request.POST.get("mobile")
        profile.sick_leave_total = request.POST.get("sick_leave_total") or 0
        profile.sick_leave_used = request.POST.get("sick_leave_used") or 0
        profile.sick_leave_remaining = request.POST.get("sick_leave_remaining") or 0
        profile.vacation_leave_total = request.POST.get("vacation_leave_total") or 0
        profile.vacation_leave_used = request.POST.get("vacation_leave_used") or 0
        profile.vacation_leave_remaining = (
            request.POST.get("vacation_leave_remaining") or 0
        )
        profile.absence_leave_total = request.POST.get("absence_leave_total") or 0
        profile.absence_leave_used = request.POST.get("absence_leave_used") or 0
        profile.absence_leave_remaining = (
            request.POST.get("absence_leave_remaining") or 0
        )
        profile.save()

        # Update user group
        selected_group = request.POST.get("user_group")
        # Remove from both groups first
        user.groups.clear()
        if selected_group:
            from django.contrib.auth.models import Group

            group = Group.objects.get(name=selected_group)
            user.groups.add(group)

        messages.success(request, "User updated successfully.")
        return redirect("user_management")

    return render(
        request,
        "accounts/edit_user.html",
        {
            "user_obj": user,  # Pass user for user fields in template
            "profile": profile,
            "is_leave_admin": is_leave_admin,
            "user_groups": user_groups,
        },
    )


@login_required(login_url="login")
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        user.delete()
        messages.success(request, "User deleted successfully.")
        return redirect("user_management")
    return render(request, "accounts/confirm_delete.html", {"user_obj": user})


@login_required(login_url="login")
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
@login_required(login_url="login")
def user_management(request):
    if not request.user.groups.filter(name="leaveAdmin").exists():
        messages.error(request, "You do not have permission to access this page.")
        return redirect("home")
    # Annotate each profile with the first group name (alphabetically)
    profiles = Profile.objects.annotate(
        group_name=Subquery(
            User.groups.through.objects.filter(user_id=OuterRef("user_id"))
            .select_related("group")
            .order_by("group__name")
            .values("group__name")[:1]
        )
    ).order_by("group_name", "user__username")
    return render(
        request, "accounts/usermng.html", {"profiles": profiles, "is_leave_admin": True}
    )


# add new user
@login_required(login_url="login")
def add_user(request):
    if not request.user.groups.filter(name="leaveAdmin").exists():
        messages.error(request, "You do not have permission to add users.")
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        password = request.POST.get("password")
        position = request.POST.get("position")
        mobile = request.POST.get("mobile")
        sick_leave_total = float(request.POST.get("sick_leave_total") or 0)
        sick_leave_used = float(request.POST.get("sick_leave_used") or 0)
        vacation_leave_total = float(request.POST.get("vacation_leave_total") or 0)
        vacation_leave_used = float(request.POST.get("vacation_leave_used") or 0)
        absence_leave_total = float(request.POST.get("absence_leave_total") or 0)
        absence_leave_used = float(request.POST.get("absence_leave_used") or 0)
        user_group = request.POST.get("user_group")
        is_active = True if request.POST.get("is_active") == "on" else False

        if not username or not password or not email:
            messages.error(request, "Username, email, and password are required.")
            return render(request, "accounts/add_user.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "accounts/add_user.html")

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
            )
            if user_group:
                group = Group.objects.get(name=user_group)
                user.groups.add(group)

            Profile.objects.create(
                user=user,
                position=position,
                mobile=mobile,
                sick_leave_total=sick_leave_total,
                sick_leave_used=sick_leave_used,
                sick_leave_remaining=max(sick_leave_total - sick_leave_used, 0),
                vacation_leave_total=vacation_leave_total,
                vacation_leave_used=vacation_leave_used,
                vacation_leave_remaining=max(
                    vacation_leave_total - vacation_leave_used, 0
                ),
                absence_leave_total=absence_leave_total,
                absence_leave_used=absence_leave_used,
                absence_leave_remaining=max(
                    absence_leave_total - absence_leave_used, 0
                ),
            )

        messages.success(request, "User added successfully.")
        return redirect("user_management")

    return render(request, "accounts/add_user.html")
