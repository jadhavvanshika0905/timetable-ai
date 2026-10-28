from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import UserProfile
from .roles import get_role

User = get_user_model()


def user_payload(user):
    profile = getattr(user, "profile", None)
    return {
        "id": user.pk, "username": user.get_username(), "role": get_role(user),
        "faculty_id": profile.faculty_id if profile else None,
        "student_id": profile.student_id if profile else None,
    }


class LoginSerializer(TokenObtainPairSerializer):
    """Normal JWT login + role inside the token and in the response body."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = get_role(user)
        token["username"] = user.get_username()
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if get_role(self.user) is None:
            raise serializers.ValidationError(
                "This account has no role yet. Ask an Admin to create its profile.")
        data["user"] = user_payload(self.user)
        return data


class CreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=UserProfile.Role.choices)
    faculty_id = serializers.IntegerField(required=False, allow_null=True)
    student_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        from apps.institution.models import Faculty, Student
        role = attrs["role"]
        fid, sid = attrs.get("faculty_id"), attrs.get("student_id")
        if role == "FACULTY":
            if not fid or not Faculty.objects.filter(pk=fid).exists():
                raise serializers.ValidationError({"faculty_id": "Valid faculty_id required."})
            if UserProfile.objects.filter(faculty_id=fid).exists():
                raise serializers.ValidationError({"faculty_id": "Already has a login."})
        elif role == "STUDENT":
            if not sid or not Student.objects.filter(pk=sid).exists():
                raise serializers.ValidationError({"student_id": "Valid student_id required."})
            if UserProfile.objects.filter(student_id=sid).exists():
                raise serializers.ValidationError({"student_id": "Already has a login."})
        elif fid or sid:
            raise serializers.ValidationError("ADMIN must not have faculty_id/student_id.")
        return attrs

    @transaction.atomic
    def create(self, validated):
        user = User.objects.create_user(username=validated["username"],
                                        password=validated["password"])
        UserProfile.objects.create(user=user, role=validated["role"],
                                   faculty_id=validated.get("faculty_id"),
                                   student_id=validated.get("student_id"))
        return user
