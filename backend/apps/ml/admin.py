from django.contrib import admin
from .models import TrainedModel, DemandPrediction, WorkloadRisk

for m in (TrainedModel, DemandPrediction, WorkloadRisk):
    admin.site.register(m)
