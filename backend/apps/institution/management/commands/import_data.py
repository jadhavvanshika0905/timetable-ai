"""python manage.py import_data <entity> <file.xlsx|csv> [--term 2026-ODD] [--dry-run]
entity: term department timeslot room faculty course student choice preference"""
from django.core.management.base import BaseCommand, CommandError

from apps.institution.importers import ORDER, import_file
from apps.institution.models import AcademicTerm


class Command(BaseCommand):
    help = "Excel/CSV se data import (poori file validate hoti hai, error pe kuch save nahi)"

    def add_arguments(self, parser):
        parser.add_argument("entity", choices=ORDER)
        parser.add_argument("path")
        parser.add_argument("--term", help="choice import ke liye AcademicTerm name")
        parser.add_argument("--dry-run", action="store_true", help="sirf validate karo, save mat karo")

    def handle(self, *args, **o):
        term = AcademicTerm.objects.filter(name=o["term"]).first() if o["term"] else None
        if o["term"] and not term:
            raise CommandError(f"Term '{o['term']}' nahi mila")
        res = import_file(o["entity"], o["path"], term=term, dry_run=o["dry_run"])
        for w in res.warnings:
            self.stdout.write(self.style.WARNING(f"  warning: {w}"))
        if res.ok:
            self.stdout.write(self.style.SUCCESS(res.summary()))
            return
        self.stdout.write(self.style.ERROR(res.summary()))
        for e in res.errors[:50]:
            self.stdout.write(f"  row {e['row']:>4} | {e['column']:<18} | {e['message']}")
        if len(res.errors) > 50:
            self.stdout.write(f"  ... aur {len(res.errors) - 50} errors")
        raise CommandError("Import fail hua")