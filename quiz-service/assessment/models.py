from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q


class Question(models.Model):
    code = models.CharField(max_length=40, unique=True)
    topic = models.CharField(max_length=100)
    prompt = models.TextField()
    options = models.JSONField(help_text='Exactly four distinct answer strings.')
    correct = models.PositiveSmallIntegerField(validators=[MaxValueValidator(3)], help_text='Correct option index: 0–3.')
    explanation = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def clean(self):
        if (not isinstance(self.options, list) or len(self.options) != 4 or
                not all(isinstance(x, str) and x.strip() for x in self.options) or len(set(self.options)) != 4):
            raise ValidationError({'options': 'Provide exactly four distinct nonempty strings.'})

    def __str__(self):
        return f'{self.code}: {self.topic}'


class Quiz(models.Model):
    title = models.CharField(max_length=200, default='Introduction to R')
    opens_at = models.DateTimeField(help_text='Europe/Brussels time in this admin; inclusive.')
    closes_at = models.DateTimeField(help_text='Hard end for login and answers; exclusive.')
    seconds_per_question = models.PositiveIntegerField(default=60, validators=[MinValueValidator(10), MaxValueValidator(3600)])
    published = models.BooleanField(default=False)
    questions = models.ManyToManyField(Question, help_text='Select exactly 100 active questions before publishing.')

    def clean(self):
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError('Closing time must be after opening time.')

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    seconds_override = models.PositiveIntegerField(null=True, blank=True,
        validators=[MinValueValidator(10), MaxValueValidator(3600)], help_text='Optional individual time allowance.')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['quiz', 'student'], name='one_enrollment')]

    def __str__(self):
        return f'{self.student} — {self.quiz}'


class Attempt(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT)
    status = models.CharField(max_length=15, default='active', choices=[(x, x) for x in ('active', 'completed', 'locked', 'void')])
    questions = models.JSONField()  # Immutable private snapshot, including shuffled answers.
    answers = models.JSONField(default=list)
    position = models.PositiveSmallIntegerField(default=0)
    seconds = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField()
    last_seen = models.DateTimeField()
    client_token = models.CharField(max_length=100)
    session_key = models.CharField(max_length=100)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['enrollment'], condition=~Q(status='void'), name='one_live_attempt')]

    @property
    def score(self):
        return sum(a['correct'] for a in self.answers)


class AuditEvent(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT)
    at = models.DateTimeField(auto_now_add=True)
    event = models.CharField(max_length=200)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
