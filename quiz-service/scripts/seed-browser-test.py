"""Disposable local/CI fixtures only. Never run against student data."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from assessment.models import Quiz, Question, Enrollment
if not settings.DEBUG or User.objects.exists() or Quiz.objects.exists():
    raise RuntimeError('Browser fixtures require DEBUG and a fresh, disposable database.')
call_command('import_bank', 'sample-bank.json')
student = User.objects.create_user('browser-student', password='local-test-password-only')
User.objects.create_superuser('browser-instructor', password='local-test-admin-only')
quiz = Quiz.objects.create(title='Introduction to R', opens_at=timezone.now()-timedelta(hours=1),
    closes_at=timezone.now()+timedelta(hours=1), seconds_per_question=10, published=True)
quiz.questions.set(Question.objects.all())
Enrollment.objects.create(student=student, quiz=quiz)
