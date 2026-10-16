from django.contrib import admin
from .models import Profile, AuditLog

admin.site.register(Profile)
admin.site.register(AuditLog)
