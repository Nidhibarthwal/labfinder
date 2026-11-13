from rest_framework import permissions


def get_type_of_logged_in_user(user):
    try:
        if user.manpower_user:
            user_type = "manpower"
    except:
        user_type = "customer"

    return user_type


class MasterObjectPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        user = request.user
        user_type = get_type_of_logged_in_user(user)
        if request.method in ['PUT', 'PATCH', 'DELETE', 'POST', 'CREATE']:
            # all_groups = [role_dept.role.group.group.name for role_dept in user.manpower_user.manpowerroles_set.all()]
            all_groups = [group.name for group in user.groups.all()]
            if 'SuperAdmin' in all_groups or 'Lab Admin' in all_groups or 'CRM' in all_groups or 'Store Admin' in all_groups:
                return bool(request.user.is_authenticated and True)
        else:
            # Allow read-only access
            return bool(request.user.is_authenticated and True)
        return bool(request.user.is_authenticated and False)
