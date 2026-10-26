"""All callers must hold an attempt/enrollment row lock inside transaction.atomic."""
import secrets
from datetime import timedelta
from .models import Attempt, AuditEvent

HEARTBEAT_GRACE = 20


def lock(attempt, now, reason):
    if attempt.status == 'active':
        attempt.status = 'locked'
        attempt.ended_at = now
        attempt.reason = reason
        attempt.save()
        AuditEvent.objects.create(attempt=attempt, event=reason)


def enforce(attempt, quiz, now):
    if attempt.status != 'active':
        return
    if not quiz.published or now < quiz.opens_at or now >= quiz.closes_at:
        lock(attempt, now, 'Assessment window closed or unpublished')
    elif (now - attempt.last_seen).total_seconds() >= HEARTBEAT_GRACE:
        lock(attempt, now, 'Connection or heartbeat absent for 20 seconds')


def start(enrollment, session_key, now):
    quiz = enrollment.quiz
    pool = list(quiz.questions.filter(active=True))
    if len(pool) != 100:
        raise ValueError('The instructor must configure exactly 100 active questions.')
    rng = secrets.SystemRandom()
    selected = []
    for q in rng.sample(pool, 10):
        order = list(range(4))
        rng.shuffle(order)
        selected.append({'code': q.code, 'topic': q.topic, 'prompt': q.prompt,
                         'options': [q.options[i] for i in order], 'correct': order.index(q.correct)})
    seconds = enrollment.seconds_override or quiz.seconds_per_question
    attempt = Attempt.objects.create(enrollment=enrollment, questions=selected, seconds=seconds,
        started_at=now, last_seen=now, deadline=min(now + timedelta(seconds=seconds), quiz.closes_at),
        session_key=session_key, client_token=secrets.token_urlsafe(32))
    AuditEvent.objects.create(attempt=attempt, event='Started', actor=enrollment.student)
    return attempt


def answer(attempt, quiz, now, choice):
    timed_out = now >= attempt.deadline
    q = attempt.questions[attempt.position]
    attempt.answers.append({'question': q['code'], 'choice': None if timed_out else choice,
        'correct': not timed_out and choice == q['correct'], 'timed_out': timed_out,
        'answered_at': now.isoformat()})
    attempt.position += 1
    if attempt.position == 10:
        attempt.status = 'completed'
        attempt.ended_at = now
        AuditEvent.objects.create(attempt=attempt, event='Completed')
    else:
        attempt.deadline = min(now + timedelta(seconds=attempt.seconds), quiz.closes_at)
    attempt.save()


def public_state(attempt, now):
    state = {'status': attempt.status, 'position': attempt.position, 'total': 10,
             'server_time': now.isoformat(), 'reason': attempt.reason}
    if attempt.status == 'active':
        q = attempt.questions[attempt.position]
        state.update(question={k: q[k] for k in ('topic', 'prompt', 'options')},
                     deadline=attempt.deadline.isoformat())
    return state
