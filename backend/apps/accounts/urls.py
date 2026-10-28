from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import lookups, views

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/users/", views.UserCreateView.as_view(), name="user-create"),
    path("terms/", lookups.TermListView.as_view(), name="terms"),
    path("lookups/", lookups.LookupsView.as_view(), name="lookups"),
    path("lookups/students/", lookups.StudentSearchView.as_view(), name="lookups-students"),
    path("timetable/generate/", views.GenerateTimetableView.as_view(), name="tt-generate"),
    path("timetable/", views.TimetableView.as_view(), name="tt-all"),
    path("timetable/mine/", views.MyTimetableView.as_view(), name="tt-mine"),
]