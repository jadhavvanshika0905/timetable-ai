from rest_framework.permissions import BasePermission

from .roles import ADMIN, FACULTY, STUDENT, get_role


class IsAdminRole(BasePermission):
    message = "Only an Admin can do this."

    def has_permission(self, request, view):
        return get_role(request.user) == ADMIN


class IsFacultyOrStudent(BasePermission):
    message = "Only Faculty or Student users can use this."

    def has_permission(self, request, view):
        return get_role(request.user) in (FACULTY, STUDENT)


class IsAnyRole(BasePermission):
    """Logged in AND has a valid role (a user with no profile is rejected)."""
    message = "Your account has no role. Ask an Admin."

    def has_permission(self, request, view):
        return get_role(request.user) is not None
