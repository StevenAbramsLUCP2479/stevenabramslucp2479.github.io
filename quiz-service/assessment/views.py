import csv
import secrets
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Quiz, Enrollment, Attempt
from . import engine


class WindowLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        now = timezone.now()
        if not user.is_staff and not Enrollment.objects.filter(student=user, quiz__published=True,
                quiz__opens_at__lte=now, quiz__closes_at__gt=now).exists():
            raise forms.ValidationError('Student login is available only during an assigned quiz window.')


class StudentLoginView(LoginView):
    authentication_form = WindowLoginForm


@login_required
def lobby(request):
    return render(request, 'assessment/lobby.html', {'enrollments': Enrollment.objects.filter(
        student=request.user, quiz__published=True).select_related('quiz')})


@login_required
def quiz_page(request, quiz_id):
    enrollment = get_object_or_404(Enrollment.objects.select_related('quiz'), quiz_id=quiz_id, student=request.user)
    with transaction.atomic():
        # A fresh document cannot take over an active page, including refresh/back/second tab.
        attempt = Attempt.objects.select_for_update().filter(enrollment=enrollment, status='active').first()
        if attempt:
            engine.lock(attempt, timezone.now(), 'Quiz page reopened, refreshed or opened in another tab')
    return render(request, 'assessment/quiz.html', {'quiz': enrollment.quiz,
        'seconds': enrollment.seconds_override or enrollment.quiz.seconds_per_question})


@login_required
@require_POST
def start_attempt(request, quiz_id):
    now = timezone.now()
    with transaction.atomic():
        enrollment = get_object_or_404(Enrollment.objects.select_for_update(), quiz_id=quiz_id, student=request.user)
        quiz = enrollment.quiz
        if not quiz.published or not quiz.opens_at <= now < quiz.closes_at:
            return JsonResponse({'error': 'This quiz is outside its access window.'}, status=403)
        if request.POST.get('consent') != 'yes':
            return JsonResponse({'error': 'Please accept the attempt rules.'}, status=400)
        existing = Attempt.objects.select_for_update().filter(enrollment=enrollment).exclude(status='void').first()
        if existing:
            engine.lock(existing, now, 'Attempt restarted or opened in another page')
            return JsonResponse(engine.public_state(existing, now))
        try:
            attempt = engine.start(enrollment, request.session.session_key, now)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=409)
        return JsonResponse({**engine.public_state(attempt, now), 'attempt_id': attempt.pk, 'token': attempt.client_token})


@login_required
@require_POST
def attempt_action(request, attempt_id, action):
    if action not in ('heartbeat', 'answer', 'lock'):
        return JsonResponse({'error': 'Unknown action.'}, status=404)
    with transaction.atomic():
        attempt = get_object_or_404(Attempt.objects.select_for_update(), pk=attempt_id,
                                   enrollment__student=request.user)
        now = timezone.now()
        if not secrets.compare_digest(request.POST.get('token', ''), attempt.client_token) or request.session.session_key != attempt.session_key:
            engine.lock(attempt, now, 'Attempt accessed from another session or page')
            return JsonResponse({'error': 'This attempt is bound to its original page and login.'}, status=403)
        quiz = attempt.enrollment.quiz
        engine.enforce(attempt, quiz, now)
        if attempt.status == 'active':
            if action == 'lock':
                engine.lock(attempt, now, 'Page departure or loss of browser focus')
            elif action == 'answer':
                try:
                    position = int(request.POST.get('position', ''))
                    raw = request.POST.get('choice', '')
                    choice = None if raw == '' else int(raw)
                    if choice not in (None, 0, 1, 2, 3):
                        raise ValueError()
                except ValueError:
                    return JsonResponse({'error': 'Invalid answer.'}, status=400)
                # Stale/double submissions cannot answer a later question.
                if position == attempt.position:
                    engine.answer(attempt, quiz, now, choice)
            if attempt.status == 'active':
                attempt.last_seen = now
                attempt.save(update_fields=['last_seen'])
        return JsonResponse(engine.public_state(attempt, now))


@login_required
@permission_required('assessment.view_attempt', raise_exception=True)
def instructor(request):
    return render(request, 'assessment/instructor.html', {'quizzes': Quiz.objects.all().order_by('-opens_at')})


def csv_safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


@login_required
@permission_required('assessment.view_attempt', raise_exception=True)
def export_results(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="r-quiz-{quiz.pk}-results.csv"'
    writer = csv.writer(response)
    writer.writerow(['attempt_id', 'student', 'quiz', 'status', 'score', 'out_of', 'started_at_utc',
                     'ended_at_utc', 'lock_reason', 'question_number', 'question_code', 'topic',
                     'prompt', 'selected_answer', 'correct_answer', 'correct', 'timed_out', 'answered_at_utc'])
    with transaction.atomic():
        for attempt in Attempt.objects.select_for_update().filter(enrollment__quiz=quiz).select_related('enrollment__student'):
            engine.enforce(attempt, quiz, timezone.now())
            for i, question in enumerate(attempt.questions):
                answer = attempt.answers[i] if i < len(attempt.answers) else {}
                choice = answer.get('choice')
                row = [attempt.pk, attempt.enrollment.student.username, quiz.title, attempt.status,
                    attempt.score, 10, attempt.started_at.isoformat(),
                    attempt.ended_at.isoformat() if attempt.ended_at else '', attempt.reason,
                    i + 1, question['code'], question['topic'], question['prompt'],
                    question['options'][choice] if choice is not None else '', question['options'][question['correct']],
                    answer.get('correct', ''), answer.get('timed_out', ''), answer.get('answered_at', '')]
                writer.writerow([csv_safe(x) for x in row])
    return response
