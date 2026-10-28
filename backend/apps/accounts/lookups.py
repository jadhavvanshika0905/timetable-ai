"""Small read-only endpoints the React app needs: terms list, faculty/course lookups, student search."""
from django.db.models import Exists, OuterRef
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserProfile
from .permissions import IsAdminRole, IsAnyRole


class TermListView(APIView):
    """GET /api/terms/  -> [{id, name, is_active}]  (any logged-in role)."""
    permission_classes = [IsAuthenticated, IsAnyRole]

    def get(self, request):
        from apps.institution.models import AcademicTerm
        return Response(list(AcademicTerm.objects.order_by("id").values("id", "name", "is_active")))


class LookupsView(APIView):
    """GET /api/lookups/  -> {faculty: [...], courses: [...]}  (Admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from apps.institution.models import Course, Faculty
        has_login = Exists(UserProfile.objects.filter(faculty=OuterRef("pk")))
        faculty = (Faculty.objects.annotate(has_login=has_login).order_by("name")
                   .values("id", "name", "employee_id", "has_login"))
        courses = Course.objects.order_by("code").values("id", "code", "name")
        return Response({"faculty": list(faculty), "courses": list(courses)})


class StudentSearchView(APIView):
    """GET /api/lookups/students/?q=21CS  -> up to 20 matches by roll number or name (Admin only)."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from django.db.models import Q
        from apps.institution.models import Student
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])
        has_login = Exists(UserProfile.objects.filter(student=OuterRef("pk")))
        rows = (Student.objects.filter(Q(roll_no__icontains=q) | Q(name__icontains=q))
                .annotate(has_login=has_login).order_by("roll_no")[:20]
                .values("id", "roll_no", "name", "has_login"))
        return Response(list(rows))