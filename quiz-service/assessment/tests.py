import csv
import io
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import Quiz, Question, Enrollment, Attempt, AuditEvent
from .views import csv_safe


@override_settings(AXES_ENABLED=False, STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class QuizTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('import_bank', str(Path(__file__).resolve().parent.parent / 'sample-bank.json'), stdout=io.StringIO())
        cls.student = User.objects.create_user('student', password='a-long-student-password')
        cls.other = User.objects.create_user('other', password='a-long-student-password')
        cls.instructor = User.objects.create_superuser('instructor', password='a-long-admin-password')
        cls.now = timezone.now()
        cls.quiz = Quiz.objects.create(opens_at=cls.now-timedelta(hours=1), closes_at=cls.now+timedelta(hours=1), published=True)
        cls.quiz.questions.set(Question.objects.all())
        cls.enrollment = Enrollment.objects.create(quiz=cls.quiz, student=cls.student)
        Enrollment.objects.create(quiz=cls.quiz, student=cls.other)

    def setUp(self):
        self.client.force_login(self.student, backend='django.contrib.auth.backends.ModelBackend')

    def start(self):
        response = self.client.post(f'/api/quiz/{self.quiz.pk}/start/', {'consent': 'yes'})
        self.assertEqual(response.status_code, 200)
        self.state = response.json()
        self.attempt = Attempt.objects.get(pk=self.state['attempt_id'])
        return self.state

    def action(self, kind, **data):
        return self.client.post(f'/api/attempt/{self.attempt.pk}/{kind}/', {'token': self.state['token'], **data})

    def test_bank_valid_and_balanced(self):
        self.assertEqual(Question.objects.count(), 100)
        self.assertEqual(Question.objects.values('topic').distinct().count(), 10)
        self.assertEqual(Question.objects.values('prompt').distinct().count(), 100)
        for q in Question.objects.all():
            q.full_clean()

    def test_random_unique_assignment_and_no_answer_key_in_response(self):
        state = self.start()
        self.assertEqual(len(self.attempt.questions), 10)
        self.assertEqual(len({q['code'] for q in self.attempt.questions}), 10)
        self.assertNotIn('correct', json.dumps(state))
        self.assertNotIn('questions', state)
        self.assertEqual(set(state['question']), {'topic', 'prompt', 'options'})
        self.client.force_login(self.other, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.post(f'/api/quiz/{self.quiz.pk}/start/', {'consent':'yes'}).json()
        other = Attempt.objects.get(pk=response['attempt_id'])
        self.assertNotEqual(other.questions, self.attempt.questions)

    def test_auth_and_enrollment_required(self):
        self.client.logout()
        self.assertEqual(self.client.post(f'/api/quiz/{self.quiz.pk}/start/').status_code, 302)
        outsider = User.objects.create_user('outsider')
        self.client.force_login(outsider, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.client.post(f'/api/quiz/{self.quiz.pk}/start/').status_code, 404)

    def test_login_window_and_staff_access(self):
        self.client.logout()
        with patch('assessment.views.timezone.now', return_value=self.quiz.opens_at-timedelta(seconds=1)):
            response = self.client.post('/login/', {'username': 'student', 'password':'a-long-student-password'})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)
            self.assertContains(response, 'only during an assigned quiz window')
            self.assertEqual(self.client.post('/login/', {'username':'instructor','password':'a-long-admin-password'}).status_code, 302)

    def test_window_boundaries_and_preexisting_session(self):
        for now in (self.quiz.opens_at-timedelta(microseconds=1), self.quiz.closes_at):
            with patch('assessment.views.timezone.now', return_value=now):
                self.assertEqual(self.client.post(f'/api/quiz/{self.quiz.pk}/start/', {'consent':'yes'}).status_code,403)
        with patch('assessment.views.timezone.now', return_value=self.quiz.opens_at):
            self.start()

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.student, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(client.post(f'/api/quiz/{self.quiz.pk}/start/', {'consent':'yes'}).status_code,403)

    def test_ten_answers_score_and_no_retake(self):
        self.start()
        for i in range(10):
            response = self.action('answer', position=i, choice=self.attempt.questions[i]['correct'])
            self.assertEqual(response.status_code,200)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status,'completed')
        self.assertEqual(self.attempt.score,10)
        self.assertNotIn('question',response.json())
        self.client.post(f'/api/quiz/{self.quiz.pk}/start/', {'consent':'yes'})
        self.assertEqual(Attempt.objects.count(),1)

    def test_late_answer_is_zero_even_if_correct(self):
        self.start()
        late = self.attempt.deadline
        Attempt.objects.filter(pk=self.attempt.pk).update(last_seen=late-timedelta(seconds=1))
        with patch('assessment.views.timezone.now', return_value=late):
            self.action('answer', position=0, choice=self.attempt.questions[0]['correct'])
        self.attempt.refresh_from_db()
        self.assertTrue(self.attempt.answers[0]['timed_out'])
        self.assertEqual(self.attempt.score,0)
        self.assertEqual(self.attempt.position,1)

    def test_duplicate_answer_does_not_answer_next_question(self):
        self.start()
        for _ in range(2):
            self.action('answer', position=0, choice=0)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.position,1)
        self.assertEqual(len(self.attempt.answers),1)

    def test_invalid_choice_rejected(self):
        self.start()
        self.assertEqual(self.action('answer',position=0,choice=9).status_code,400)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.position,0)

    def test_lock_is_permanent_and_reload_locks(self):
        self.start()
        self.client.get(f'/quiz/{self.quiz.pk}/')
        self.assertEqual(self.action('answer',position=0,choice=0).json()['status'],'locked')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.answers,[])
        self.assertTrue(AuditEvent.objects.filter(attempt=self.attempt,event__contains='reopened').exists())

    def test_departure_endpoint_and_heartbeat_gap(self):
        self.start()
        self.assertEqual(self.action('lock').json()['status'],'locked')
        self.assertEqual(self.action('heartbeat').json()['status'],'locked')

    def test_disconnect_locks_on_next_request(self):
        self.start()
        with patch('assessment.views.timezone.now', return_value=self.attempt.last_seen+timedelta(seconds=20)):
            state = self.action('heartbeat').json()
        self.assertEqual(state['status'],'locked')
        self.assertIn('heartbeat',state['reason'])

    def test_hard_window_end(self):
        self.start()
        with patch('assessment.views.timezone.now', return_value=self.quiz.closes_at):
            self.assertEqual(self.action('answer',position=0,choice=0).json()['status'],'locked')

    def test_no_access_to_other_students_attempt(self):
        self.start()
        self.client.force_login(self.other, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.action('heartbeat').status_code,404)

    def test_another_login_session_locks_attempt(self):
        self.start()
        self.client.logout()
        self.client.force_login(self.student, backend='django.contrib.auth.backends.ModelBackend')
        self.assertEqual(self.action('heartbeat').status_code,403)
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status,'locked')

    def test_individual_time_allowance(self):
        self.enrollment.seconds_override=120
        self.enrollment.save()
        self.start()
        self.assertEqual(self.attempt.seconds,120)
        self.assertEqual((self.attempt.deadline-self.attempt.started_at).total_seconds(),120)

    def test_window_caps_question_deadline(self):
        with patch('assessment.views.timezone.now', return_value=self.quiz.closes_at-timedelta(seconds=5)):
            self.start()
        self.assertEqual(self.attempt.deadline,self.quiz.closes_at)

    def test_missing_bank_prevents_start(self):
        self.quiz.questions.remove(Question.objects.first())
        self.assertEqual(self.client.post(f'/api/quiz/{self.quiz.pk}/start/', {'consent':'yes'}).status_code,409)
        self.assertFalse(Attempt.objects.exists())

    def test_private_results_and_csv(self):
        self.start()
        self.action('answer',position=0,choice=self.attempt.questions[0]['correct'])
        url=f'/instructor/{self.quiz.pk}/results.csv'
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.instructor, backend='django.contrib.auth.backends.ModelBackend')
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        rows=list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows),10)
        self.assertEqual(rows[0]['score'],'1')
        self.assertEqual(rows[0]['student'],'student')
        self.assertEqual(rows[0]['correct'],'True')
        self.assertEqual(csv_safe('=SUM(A1:A2)'),"'=SUM(A1:A2)")
        self.assertEqual(csv_safe('  @SUM(A1:A2)'),"'  @SUM(A1:A2)")

    def test_retake_retains_old_record(self):
        self.start()
        self.action('lock')
        old=self.attempt
        from .admin import AttemptAdmin
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        request=RequestFactory().post('/admin/')
        request.user=self.instructor
        model_admin=AttemptAdmin(Attempt,AdminSite())
        with patch.object(model_admin,'message_user'):
            model_admin.authorize_retake(request,Attempt.objects.filter(pk=old.pk))
        self.start()
        old.refresh_from_db()
        self.assertEqual(old.status,'void')
        self.assertNotEqual(old.pk,self.attempt.pk)
        self.assertEqual(Attempt.objects.count(),2)

    def test_bank_edit_cannot_change_active_question(self):
        self.start()
        before=self.attempt.questions
        Question.objects.all().update(prompt='edited')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.questions,before)

    def test_expiry_command(self):
        self.start()
        Attempt.objects.filter(pk=self.attempt.pk).update(last_seen=timezone.now()-timedelta(minutes=1))
        call_command('expire_attempts')
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status,'locked')

    def test_one_live_attempt_constraint(self):
        self.start()
        with self.assertRaises(IntegrityError),transaction.atomic():
            self.attempt.pk=None
            self.attempt.save()

    def test_import_roster_keeps_existing_password_and_enrolls_new_user(self):
        import tempfile
        from django.core.management.base import CommandError
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent) as directory:
            roster=Path(directory)/'roster.csv'
            credentials=Path(directory)/'credentials.csv'
            roster.write_text('username,seconds_override\nnew-student,90\nstudent,120\n')
            call_command('import_students',self.quiz.pk,str(roster),credentials=str(credentials),stdout=io.StringIO())
            rows=list(csv.DictReader(io.StringIO(credentials.read_text())))
            self.assertEqual(len(rows),1)
            self.assertTrue(User.objects.get(username='new-student').check_password(rows[0]['temporary_password']))
            self.assertTrue(User.objects.get(username='student').check_password('a-long-student-password'))
            self.assertEqual(credentials.stat().st_mode & 0o777,0o600)
            self.assertEqual(Enrollment.objects.get(student__username='new-student').seconds_override,90)
            with self.assertRaises(CommandError):
                call_command('import_students',self.quiz.pk,str(roster),credentials=str(credentials))
            self.assertTrue(credentials.exists())

    def test_bad_bank_rolls_back_all_changes(self):
        import tempfile
        from django.core.management.base import CommandError
        bank=json.loads((Path(__file__).resolve().parent.parent/'sample-bank.json').read_text())
        bank[0]['prompt']='Must roll back'
        bank[-1]['options']=['invalid']
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json',dir=Path(__file__).resolve().parent.parent) as source:
            json.dump(bank,source);source.flush()
            with self.assertRaises(CommandError):
                call_command('import_bank',source.name)
        self.assertNotEqual(Question.objects.get(code='R001').prompt,'Must roll back')

    @override_settings(AXES_ENABLED=True)
    def test_repeated_bad_password_locks_login(self):
        self.client.logout()
        for _ in range(5):
            self.client.post('/login/', {'username':'student','password':'incorrect'})
        response=self.client.post('/login/', {'username':'student','password':'a-long-student-password'})
        self.assertEqual(response.status_code,429)
        self.assertNotIn('_auth_user_id',self.client.session)


from django.test import TransactionTestCase, skipUnlessDBFeature
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


@override_settings(AXES_ENABLED=False)
@skipUnlessDBFeature('has_select_for_update')
class ConcurrentAttemptTests(TransactionTestCase):
    def setUp(self):
        call_command('import_bank',str(Path(__file__).resolve().parent.parent/'sample-bank.json'),stdout=io.StringIO())
        self.user=User.objects.create_user('parallel-student')
        now=timezone.now()
        self.quiz=Quiz.objects.create(opens_at=now-timedelta(minutes=1),closes_at=now+timedelta(hours=1),published=True)
        self.quiz.questions.set(Question.objects.all())
        Enrollment.objects.create(quiz=self.quiz,student=self.user)
        self.clients=[Client(),Client()]
        for client in self.clients:
            client.force_login(self.user,backend='django.contrib.auth.backends.ModelBackend')

    def parallel(self, fn):
        barrier=Barrier(2)
        def run(client):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return fn(client)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run,self.clients))

    def test_simultaneous_starts_create_only_one_attempt(self):
        results=self.parallel(lambda client:client.post(f'/api/quiz/{self.quiz.pk}/start/',{'consent':'yes'}).status_code)
        self.assertEqual(results,[200,200])
        self.assertEqual(Attempt.objects.count(),1)
        self.assertEqual(Attempt.objects.get().status,'locked')

    def test_simultaneous_answers_advance_only_once(self):
        state=self.clients[0].post(f'/api/quiz/{self.quiz.pk}/start/',{'consent':'yes'}).json()
        self.clients[1].cookies=self.clients[0].cookies.copy()
        results=self.parallel(lambda client:client.post(f'/api/attempt/{state["attempt_id"]}/answer/',
            {'token':state['token'],'position':0,'choice':0}).status_code)
        self.assertEqual(results,[200,200])
        attempt=Attempt.objects.get()
        self.assertEqual(attempt.position,1)
        self.assertEqual(len(attempt.answers),1)
