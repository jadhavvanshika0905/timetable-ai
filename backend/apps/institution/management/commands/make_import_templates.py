"""python manage.py make_import_templates  -> apps/institution/templates_xlsx/<entity>_template.xlsx"""
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.institution.importers import ORDER, build_template


class Command(BaseCommand):
    help = "Har entity ka blank Excel template banata hai"

    def handle(self, *args, **o):
        out = Path(__file__).resolve().parents[2] / "templates_xlsx"
        out.mkdir(exist_ok=True)
        for e in ORDER:
            (out / f"{e}_template.xlsx").write_bytes(build_template(e))
            self.stdout.write(f"  {e}_template.xlsx")
        self.stdout.write(self.style.SUCCESS(f"Templates ready: {out}"))