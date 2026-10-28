from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import timetable_access as access
from .permissions import IsAdminRole, IsAnyRole
from .serializers import CreateUserSerializer, LoginSerializer, user_payload


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = LoginSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated, IsAnyRole]

    def get(self, request):
        return Response(user_payload(request.user))


class UserCreateView(APIView):
    """Admin creates Faculty / Student / Admin logins."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        ser = CreateUserSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(user_payload(user), status=status.HTTP_201_CREATED)


def _term_id(request):
    raw = request.query_params.get("term_id") or request.data.get("term_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class GenerateTimetableView(APIView):
    """Admin only.  Body: {term_id, course_ids?, max_time_seconds?, use_ml?}"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        term_id = _term_id(request)
        if term_id is None:
            return Response({"detail": "term_id is required."}, status=400)
        try:
            seconds = min(float(request.data.get("max_time_seconds", 30)), 300.0)
        except (TypeError, ValueError):
            return Response({"detail": "max_time_seconds must be a number."}, status=400)
        from apps.ml.service import generate_with_ml
        from apps.scheduler.services import SchedulerDataError
        try:
            out = generate_with_ml(
                term_id, course_ids=request.data.get("course_ids"),
                max_time_seconds=seconds, use_ml=bool(request.data.get("use_ml", True)))
        except SchedulerDataError as exc:
            return Response({"detail": str(exc)}, status=400)
        result = out["result"]
        saved = result["status"] in ("OPTIMAL", "FEASIBLE")
        if saved:
            access.save_timetable(term_id, result)
        hints = out["ml_hints"]
        return Response({
            "status": result["status"], "saved": saved, "rows": len(result["timetable"]),
            "metrics": result.get("metrics", {}),
            "infeasibility_reasons": result.get("infeasibility_reasons", []),
            "ml_hints": ({k: v for k, v in hints.items() if not k.startswith("_")}
                         if hints else None),
        })


class TimetableView(APIView):
    """Admin: the whole timetable of a term."""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        term_id = _term_id(request)
        if term_id is None:
            return Response({"detail": "term_id is required."}, status=400)
        stored = access.get_timetable(term_id)
        if not stored:
            return Response({"detail": "No timetable generated for this term yet."}, status=404)
        return Response({"term_id": term_id, "status": stored["status"],
                         "timetable": access.enrich(stored["timetable"])})


class MyTimetableView(APIView):
    """Faculty/Student: only their own rows.  Admin: everything."""
    permission_classes = [IsAuthenticated, IsAnyRole]

    def get(self, request):
        term_id = _term_id(request)
        if term_id is None:
            return Response({"detail": "term_id is required."}, status=400)
        stored = access.get_timetable(term_id)
        if not stored:
            return Response({"detail": "No timetable generated for this term yet."}, status=404)
        rows = access.rows_for_user(request.user, term_id, stored["timetable"])
        return Response({"term_id": term_id, "role": user_payload(request.user)["role"],
                         "timetable": access.enrich(rows)})
