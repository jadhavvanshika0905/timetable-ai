"""PART 2 - ML predictions (SRS 4.3). Admin inhe override kar sakta hai (REQ-3.4)."""
from django.db import models


class TrainedModel(models.Model):
    name = models.CharField(max_length=50)            # "demand" / "workload"
    version = models.CharField(max_length=20)
    file_path = models.CharField(max_length=255)      # saved_models/xxx.joblib
    metrics = models.JSONField(default=dict, blank=True)  # {"mae": 3.2, "r2": 0.81}
    trained_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trained_at"]

    def __str__(self):
        return f"{self.name} v{self.version}"


class DemandPrediction(models.Model):
    term = models.ForeignKey("institution.AcademicTerm", on_delete=models.CASCADE)
    course = models.ForeignKey("institution.Course", on_delete=models.CASCADE)
    predicted_students = models.PositiveIntegerField()
    override_value = models.PositiveIntegerField(null=True, blank=True)
    model_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["term", "course"], name="uniq_demand_term_course")]

    @property
    def final_value(self):
        return self.override_value if self.override_value is not None else self.predicted_students


class WorkloadRisk(models.Model):
    class Level(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    term = models.ForeignKey("institution.AcademicTerm", on_delete=models.CASCADE)
    faculty = models.ForeignKey("institution.Faculty", on_delete=models.CASCADE)
    risk_level = models.CharField(max_length=6, choices=Level.choices)
    score = models.FloatField(default=0.0)
    override_level = models.CharField(max_length=6, choices=Level.choices, blank=True)
    model_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["term", "faculty"], name="uniq_risk_term_faculty")]

    @property
    def final_level(self):
        return self.override_level or self.risk_level
