import csv
import os
import secrets
from pathlib import Path
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from assessment.models import Quiz, Enrollment


class Command(BaseCommand):
    help = 'Enroll usernames from CSV; create random passwords for NEW users in a private output file.'

    def add_arguments(self, parser):
        parser.add_argument('quiz_id', type=int)
        parser.add_argument('csv_path')
        parser.add_argument('--credentials', required=True, help='New private CSV path, created with mode 0600.')

    def handle(self, *args, **options):
        output = Path(options['credentials'])
        if output.exists():
            raise CommandError('Credentials file already exists; choose a new path.')
        created_output = False
        try:
            with open(options['csv_path'], newline='', encoding='utf-8-sig') as source:
                rows = list(csv.DictReader(source))
            if not rows or any(not row.get('username', '').strip() for row in rows):
                raise ValueError('CSV must contain a username column and nonempty rows.')
            with transaction.atomic():
                quiz = Quiz.objects.get(pk=options['quiz_id'])
                descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                created_output = True
                with os.fdopen(descriptor, 'w', newline='', encoding='utf-8') as target:
                    writer = csv.writer(target)
                    writer.writerow(['username', 'temporary_password'])
                    for row in rows:
                        username = row['username'].strip()
                        user = User.objects.filter(username=username).first()
                        if user is None:
                            password = secrets.token_urlsafe(18)
                            user = User(username=username)
                            user.set_password(password)
                            user.full_clean()
                            user.save()
                            writer.writerow([username, password])
                        elif user.is_staff or user.is_superuser:
                            raise ValueError('Use separate student accounts, not instructor accounts.')
                        enrollment, _ = Enrollment.objects.get_or_create(quiz=quiz, student=user)
                        if row.get('seconds_override', '').strip():
                            enrollment.seconds_override = int(row['seconds_override'])
                        enrollment.full_clean()
                        enrollment.save()
        except Exception as exc:
            if created_output:
                output.unlink(missing_ok=True)
            raise CommandError(f'Import failed; database changes rolled back: {exc}') from exc
        self.stdout.write(self.style.SUCCESS('Students enrolled. Deliver credentials privately; do not commit either CSV.'))
