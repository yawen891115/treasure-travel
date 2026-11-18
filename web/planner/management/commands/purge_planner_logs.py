"""Operator-controlled retention; dry-run unless --apply is explicitly supplied."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from planner.models import PlaceFeedback, TripLog


class Command(BaseCommand):
    help = "Preview or delete planner logs/feedback older than N days (default: dry-run)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["days"] < 1:
            raise CommandError("--days must be at least 1")
        cutoff = timezone.now() - timedelta(days=options["days"])
        for model in [TripLog, PlaceFeedback]:
            records = model.objects.filter(created_at__lt=cutoff)
            count = records.count()
            if options["apply"]:
                records.delete()
            self.stdout.write(
                f"{'Deleted' if options['apply'] else 'Would delete'} "
                f"{count} {model.__name__} records"
            )
