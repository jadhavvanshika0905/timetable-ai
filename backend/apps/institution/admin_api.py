"""Admin-only API used by the React 'Data setup' page. Mounted at /api/admin-data/ (see admin_urls.py)."""
import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.http import HttpResponse
from django.urls import include, path
from rest_framework import serializers, status, viewsets
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView

from .importers import ORDER, SPECS, build_template, import_file
from .models import (AcademicTerm, Course, Department, Faculty, FacultyPreference, Room,
                     Student, StudentCourseChoice, TimeSlot)
from django.db.models import ProtectedError


class IsAdminRole(BasePermission):
    """Django superuser, or a login whose UserProfile.role == ADMIN."""
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.is_superuser:
            return True
        p = getattr(u, "profile", None)
        return bool(p and p.role == "ADMIN")


# resource name -> (model, search fields)
RESOURCES = {
    "departments": (Department, ["code", "name"]),
    "terms": (AcademicTerm, ["name"]),
    "faculty": (Faculty, ["employee_id", "name"]),
    "rooms": (Room, ["code", "name"]),
    "courses": (Course, ["code", "name"]),
    "students": (Student, ["roll_no", "name"]),
    "timeslots": (TimeSlot, ["day"]),
    "choices": (StudentCourseChoice, ["student__roll_no", "course__code"]),
    "preferences": (FacultyPreference, ["faculty__employee_id"]),
}


def make_viewset(model, search_fields):
    class S(serializers.ModelSerializer):
        class Meta:
            fields = "__all__"
    S.Meta.model = model

    class V(viewsets.ModelViewSet):
        queryset = model.objects.all().order_by("pk")
        serializer_class = S
        permission_classes = [IsAdminRole]
        pagination_class = None

        def list(self, request, *a, **kw):
            qs = self.get_queryset()
            q = request.query_params.get("q", "").strip()
            if q:
                cond = Q()
                for f in search_fields:
                    cond |= Q(**{f"{f}__icontains": q})
                qs = qs.filter(cond)
            total = qs.count()
            limit = min(int(request.query_params.get("limit", 200) or 200), 2000)
            return Response({"count": total, "results": S(qs[:limit], many=True).data})

        def _save(self, serializer):
            try:
                with transaction.atomic():
                    obj = serializer.save()
                    obj.full_clean()          # runs model.clean() e.g. Course lab rules
            except DjangoValidationError as e:
                raise serializers.ValidationError(e.message_dict if hasattr(e, "error_dict") else e.messages)

        def perform_create(self, serializer):
            self._save(serializer)

        def perform_update(self, serializer):
            self._save(serializer)

        def destroy(self, request, *a, **kw):
            try:
                return super().destroy(request, *a, **kw)
            except ProtectedError:
                return Response({"detail": "Cannot delete: other records still use this one."},
                                status=status.HTTP_409_CONFLICT)

    V.__name__ = f"{model.__name__}AdminViewSet"
    return V


class ImportView(APIView):
    """POST file + entity (+ dry_run). Uses importers.import_file: validate whole file, save all or nothing."""
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    def post(self, request):
        f = request.FILES.get("file")
        entity = request.data.get("entity", "")
        if not f:
            return Response({"detail": "Choose a file first."}, status=400)
        if entity not in SPECS:
            return Response({"detail": "Choose what this file contains: " + ", ".join(ORDER)}, status=400)
        dry = str(request.data.get("dry_run", "")).lower() in ("1", "true", "yes")
        try:
            res = import_file(entity, f, dry_run=dry, filename=f.name)
        except Exception:  # noqa: BLE001 - unreadable/corrupt file
            return Response({"detail": "Could not read this file. Use a valid .xlsx or .csv."}, status=400)
        data = res.as_dict()
        data["errors"] = data["errors"][:200]
        if not res.ok:
            data["detail"] = f"{len(res.errors)} problem(s) found. Nothing was saved."
            return Response(data, status=422)
        return Response(data)


class TemplateView(APIView):
    """GET templates/<entity>/ -> .xlsx template (header, example row, help sheet)."""
    permission_classes = [IsAdminRole]

    def get(self, request, entity):
        if entity not in SPECS:
            return Response({"detail": "Unknown template."}, status=404)
        resp = HttpResponse(build_template(entity),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="{entity}_template.xlsx"'
        return resp


def generate_slots(days, periods, first_start, minutes, lunch_after, lunch_minutes, replace):
    """Mon..Sat x periods; a lunch row (is_break=True) is inserted after `lunch_after` periods."""
    cur0 = datetime.datetime.combine(datetime.date.today(), first_start)
    made = 0
    with transaction.atomic():
        if replace:
            TimeSlot.objects.all().delete()   # cascades to preferences / timetable entries
        for d in days:
            cur, p = cur0, 1
            for i in range(1, periods + 1):
                end = cur + datetime.timedelta(minutes=minutes)
                TimeSlot.objects.update_or_create(day=d, period=p, defaults={
                    "start_time": cur.time(), "end_time": end.time(), "is_break": False})
                made += 1
                cur, p = end, p + 1
                if lunch_after and i == lunch_after and lunch_minutes:
                    end = cur + datetime.timedelta(minutes=lunch_minutes)
                    TimeSlot.objects.update_or_create(day=d, period=p, defaults={
                        "start_time": cur.time(), "end_time": end.time(), "is_break": True})
                    cur, p = end, p + 1
    return made


class SummaryView(APIView):
    """Counts + 'is the data ready for the solver?' warnings."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        counts = {k: m.objects.count() for k, (m, _) in RESOURCES.items()}
        warnings = []
        term = AcademicTerm.objects.filter(is_active=True).first()
        if not term:
            warnings.append("No active academic term. Add a term and mark it active.")
        class_slots = TimeSlot.objects.filter(is_break=False).count()
        if not class_slots:
            warnings.append("No time slots yet. Use 'Create a standard week' or upload timeslots.")
        if not Room.objects.exists():
            warnings.append("No rooms added.")
        no_fac = Course.objects.filter(faculty__isnull=True).count()
        if no_fac:
            warnings.append(f"{no_fac} course(s) have no faculty assigned.")
        max_cap = Room.objects.aggregate(m=Max("capacity"))["m"] or 0
        big = Course.objects.filter(expected_students__gt=max_cap).count() if max_cap else 0
        if big:
            warnings.append(f"{big} course(s) expect more students than the biggest room ({max_cap}).")
        if Course.objects.filter(requires_lab=True).exists() and not Room.objects.filter(room_type="LAB").exists():
            warnings.append("Some courses need a lab but there is no LAB room.")
        for f in Faculty.objects.annotate(h=Sum("courses__hours_per_week")):
            if f.h and f.h > f.max_hours_per_week:
                warnings.append(f"{f.name} is assigned {f.h} h/week but the limit is {f.max_hours_per_week}.")
        if term and not StudentCourseChoice.objects.filter(term=term).exists():
            warnings.append("No student course choices for the active term. Student clash checks will be skipped.")
        need = Course.objects.aggregate(h=Sum("hours_per_week"))["h"] or 0
        have = class_slots * Room.objects.count()
        if have and need > have:
            warnings.append(f"Courses need {need} room-periods per week but only {have} exist.")
        return Response({"counts": counts, "warnings": warnings,
                         "active_term": {"id": term.id, "name": term.name} if term else None,
                         "ready": bool(term and class_slots and counts["rooms"] and counts["courses"])})


class SlotsView(APIView):
    permission_classes = [IsAdminRole]
    parser_classes = [JSONParser]

    def post(self, request):
        d = request.data
        try:
            days = [x for x in d.get("days", ["Mon", "Tue", "Wed", "Thu", "Fri"]) if x in TimeSlot.Day.values]
            periods = int(d.get("periods", 6))
            minutes = int(d.get("minutes", 50))
            lunch_after = int(d.get("lunch_after", 3))
            lunch_minutes = int(d.get("lunch_minutes", 45))
            h, m = str(d.get("first_start", "09:00")).split(":")
            first = datetime.time(int(h), int(m))
        except (ValueError, TypeError):
            return Response({"detail": "Check the numbers and start time."}, status=400)
        if not days or not (1 <= periods <= 12) or not (20 <= minutes <= 180):
            return Response({"detail": "Pick at least one day, 1-12 periods, 20-180 minutes each."}, status=400)
        n = generate_slots(days, periods, first, minutes, lunch_after, lunch_minutes,
                               bool(d.get("replace", False)))
        return Response({"ok": True, "classes_slots": n})


def build_urlpatterns():
    router = DefaultRouter()
    for name, (model, search) in RESOURCES.items():
        router.register(name, make_viewset(model, search), basename=f"admindata-{name}")
    return [
        path("import/", ImportView.as_view()),
        path("templates/<str:entity>/", TemplateView.as_view()),
        path("summary/", SummaryView.as_view()),
        path("slots/generate/", SlotsView.as_view()),
        path("", include(router.urls)),
    ]