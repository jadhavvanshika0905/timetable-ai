"""Single place that answers: what role does this user have?"""
ADMIN, FACULTY, STUDENT = "ADMIN", "FACULTY", "STUDENT"


def get_role(user):
    if not user or not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser:
        return ADMIN
    profile = getattr(user, "profile", None)      # reverse OneToOne; None if missing
    return profile.role if profile else None
