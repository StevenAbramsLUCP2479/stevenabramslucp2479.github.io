from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from assessment.models import Attempt
from assessment.engine import enforce


class Command(BaseCommand):
    help = 'Persist expired-window/heartbeat locks. Run every minute in production.'

    def handle(self, *args, **options):
        with transaction.atomic():
            for attempt in Attempt.objects.select_for_update().filter(status='active'):
                enforce(attempt, attempt.enrollment.quiz, timezone.now())
