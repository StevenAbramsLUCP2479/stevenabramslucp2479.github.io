# Timed introduction-to-R quiz

This service adds student accounts, a 100-question bank, random sets of 10, server-enforced question timers, an access window, locked attempts and instructor CSV downloads. The personal website has a landing page at `/r-quiz/` and links to this service after its URL is configured.

**Merging this PR does not deploy the backend.** GitHub Pages cannot run Django, store private results or enforce authentication. Deploy the service on an institution-managed HTTPS host with PostgreSQL, then set `r_quiz_url` in the website's `_config.yml` to its HTTPS URL. Leave that setting empty until deployment and a student/instructor smoke test are complete. No external infrastructure is created by this repository.

## What students experience

1. Use an individual username and password supplied privately by the instructor. There is no public registration. Student login requires an assigned, published quiz whose window is currently open.
2. Read the rules and explicitly start. The server selects 10 distinct questions without replacement from the quiz's 100 active questions and shuffles their options. Students can receive overlapping questions; unique sets across a class are not guaranteed.
3. Answer one multiple-choice question at a time. No R installation is needed and no student R code is executed. Timers begin when the server sends each question; submit immediately to advance. Expired or unanswered questions receive zero points. Each correct answer is worth one point, total 10.
4. Submitted answers cannot be revisited. Only the current question is delivered to the browser; correct answers, future questions and scores are not returned by the student API.
5. Switching tabs/windows, minimizing, refreshing, navigating away or closing the page locks an active attempt. A visible page sends a heartbeat every five seconds; a gap of 20 seconds locks the attempt on the next request, export or scheduled expiry run. A question's time and the quiz closing time continue during connection problems. The closing time is a hard cutoff, including for students who started late.
6. Completion confirms that answers were saved. Scores are downloaded and communicated by the instructor.

This is browser event monitoring, **not a lockdown browser or proctoring system**. It cannot stop operating-system navigation, another device, developer tools or a modified client. Browser/OS dialogs and assistive technology can trigger focus loss, and network problems can lock honest students. Review the audit record rather than interpreting a lock as proof of misconduct. Use an institution-approved exam environment for high-stakes assessments, and arrange accommodations before the assessment.

## The public sample bank

`sample-bank.json` contains 100 original introductory questions, ten in each of ten topics. `scripts/check-bank.R` verifies each answer's R semantics. The reference scope is [An Introduction to R](https://cran.r-project.org/doc/manuals/r-release/R-intro.html).

**This repository is public: its sample questions and answer keys are publicly readable, even though Jekyll excludes `quiz-service/` from the built website.** For graded assessment, create an independently authored bank in a private file outside Git, import it directly into the database, and select those questions for the quiz. The sample bank is suitable as a transparent practice bank. Its codes are `R001`–`R100`; use different codes for an additional bank. Import is transactional and requires exactly 100 valid entries with unique codes. Import does not alter quiz membership or publish anything.

Private-bank schema (100 entries):

```json
[{"code":"PRIVATE001","topic":"Data types","prompt":"Your question", "options":["A","B","C","D"], "correct":0,"explanation":"Instructor explanation"}]
```

`correct` is a zero-based option index. `check` is used only by the trusted sample-bank test script and is not evaluated by the application/importer. Never run the R checker against an untrusted bank. Existing attempts retain their original private question snapshots, even if questions are subsequently edited.

## Local preview

Python 3.12 or later:

```sh
cd quiz-service
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export QUIZ_DEBUG=1
python manage.py migrate
python manage.py import_bank sample-bank.json
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000/admin/`. SQLite is supported only for local preview/tests; production refuses to run without PostgreSQL, whose row locks protect concurrent submissions. Do not expose the development server or set `QUIZ_DEBUG=1` in production.

## Deploy with Docker Compose

The included stack runs Django/Gunicorn, PostgreSQL and Caddy HTTPS, with persistent volumes for the database and certificates. It also runs expiry checks every minute. You need a server with Docker Compose, a DNS hostname pointing to it, and ports 80/443 available. Only Caddy is publicly exposed.

1. Copy `quiz-service/` to the server and work in that directory.
2. Copy `.env.example` to `.env`. Set `QUIZ_HOST` to the actual hostname (no scheme or slash). Generate **two different** secrets with `python -c 'import secrets; print(secrets.token_urlsafe(48))'` and use them for `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. Keep `.env` private, e.g. `chmod 600 .env`.
3. Build and initialize:

   ```sh
   docker compose build
   docker compose run --rm app python manage.py migrate
   docker compose run --rm app python manage.py createsuperuser
   docker compose run --rm app python manage.py import_bank sample-bank.json
   docker compose run --rm app python manage.py check --deploy --fail-level WARNING
   docker compose up -d
   ```

4. For a private bank, copy it securely to the host and import with a read-only mount:

   ```sh
   docker compose run --rm -v /absolute/private/bank.json:/tmp/bank.json:ro app python manage.py import_bank /tmp/bank.json
   ```

5. Visit `https://YOUR_HOST/admin/` and configure the quiz and students below. Test student login, completion, a deliberate tab departure, a retake and CSV download with test accounts. Test from a separate device over HTTPS.
6. Set `r_quiz_url: "https://YOUR_HOST/"` in the personal website's `_config.yml` and deploy that website change.

For another hosting platform, deploy `config.wsgi:application` with Gunicorn, run migrations/collectstatic, and set the environment variables shown in `.env.example` plus `DATABASE_URL`. Use PostgreSQL with TLS (`PGSSLMODE=require`, the default). Enable `TRUST_PROXY=1` only behind a trusted proxy that strips and sets `X-Forwarded-Proto`; the supplied Compose stack handles this with Caddy. Do not expose the app port directly when proxy trust is enabled. Run `python manage.py expire_attempts` every minute and `python manage.py clearsessions` daily. Keep application and database clocks synchronized.

The Compose database uses an internal, unexposed network connection and `PGSSLMODE=disable`; do not carry that setting over to a remote database. Store encrypted backups outside the container host and test restoration. Do not remove the `quiz-db` volume during upgrades.

## Instructor workflow

At `/admin/`, sign in with your superuser account. Admin controls use Europe/Brussels time; exports use UTC timestamps. All window comparisons are timezone-aware. Check the daylight-saving offset when scheduling near a clock change.

1. Under **Quizzes**, add a quiz. Set opening and closing dates/times and **Seconds per question** (10–3600, default 60). The default 60 seconds is only a starting value; adapt it to your course. Select exactly 100 active questions and save.
2. Under **Users**, create student accounts with separate, strong passwords; leave **Staff status** and **Superuser status** off. Under **Enrollments**, assign each student to the quiz. An optional **Seconds override** gives an individual time allowance; it is copied at attempt start. Leave enough time in the overall quiz window for that allowance.
3. Mark the quiz **Published** when ready. Access is still restricted to its scheduled window. There is no publishing step that emails students.
4. For a roster, use the `import_students` command instead of manual account creation:

   ```sh
   python manage.py import_students 1 /private/roster.csv --credentials /private/new-credentials.csv
   ```

   The input has `username,seconds_override` headers; the time override is optional. Existing student passwords are preserved. New accounts receive random passwords, written only to a new file with mode 0600, never printed to logs. Deliver them individually through an approved private channel. With Docker, mount your private directory and ensure UID 10001 can write the output file. Never commit rosters, credentials, responses or private banks. Delete the temporary credentials file after secure delivery. For forgotten passwords use the user's password-change form in the admin.
5. Go to `/instructor/` and click **Download results CSV** for a quiz. The CSV has one row per assigned question and includes student username, attempt ID/status, total score, selected and correct answers, question text, timestamps, timeout flags and lock reason. Unanswered rows remain blank and contribute zero to the total. `void` attempts remain in the export; exclude them from final grades. A student who never started has no attempt rows; compare against the enrollment roster for absences. CSV formula-prefix escaping protects spreadsheet imports.
6. After a genuine technical issue, open **Attempts**, select the **locked** record and use **Authorize a fresh attempt**. The old record becomes `void`, an audit event identifies the instructor, and the student may start a new random set within the original access window. Completed attempts cannot be reset through this action. Never delete records to hide an earlier attempt.

For a teaching assistant, create a staff account and grant only the required model permissions. Viewing/downloading results requires `assessment.view_attempt`; authorizing retakes also requires `assessment.change_attempt`. A superuser can perform all instructor operations. Keep instructor and student accounts separate. Use the framework's admin log and the attempt audit events to review administrative changes.

Changing an active quiz's closing time or publication status takes effect on subsequent requests; question duration and question content are snapshotted at start. Avoid changing settings during an assessment. If an accommodation is needed mid-attempt, lock/review the attempt and authorize a fresh attempt after updating the enrollment.

## Security and maintenance

- Password hashes, login rate limiting, server sessions, CSRF checks, permission checks, HTTPS-only cookies, no-store responses and a same-origin content policy are enabled. No third-party scripts or trackers run in the quiz.
- Login rate limiting is per username (five failures, 15-minute cooldown), including the admin. This deliberately avoids blocking a whole class behind one campus IP. `axes.W006` is silenced for that documented policy; username limits still apply when the source IP changes. An instructor can reset login lockouts in the Axes admin.
- PostgreSQL row locks and a uniqueness constraint prevent duplicate live attempts. Answers carry a question position, so repeated submissions cannot answer the next question. The server owns sampling, timing, grades and lock state.
- A page token plus login session binds the attempt to the original document. Reloading the quiz locks the attempt. Browser monitoring can be bypassed by a technically skilled user, as described above.
- Restrict database access, back up student data, and agree an institutional retention period. Store only the needed student identifier. Schedule deletion/anonymization of expired course records under your institution's process; no automatic retention period is guessed by this project.
- Dependencies are pinned in `requirements.txt`. Update security patches regularly and run the full tests before deploying them.
- Run Django's [deployment checks](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/) for the actual host. Review [page visibility limitations](https://developer.mozilla.org/en-US/docs/Web/API/Document/visibilitychange_event) before using focus locks in an assessment policy.

## Verification

```sh
QUIZ_DEBUG=1 python manage.py test assessment --verbosity 2
QUIZ_DEBUG=1 python manage.py makemigrations --check --dry-run
node --check assessment/static/assessment/quiz.js
Rscript scripts/check-bank.R # requires jsonlite; trusted sample bank only
```

GitHub Actions runs the backend suite with PostgreSQL, production security checks and all 100 R answer checks. A Chromium smoke test exercises the student flow, automatic timeout, focus lock, restart prevention, instructor CSV, admin question selector and a mobile viewport; screenshots are retained as a workflow artifact. The existing Jekyll build checks the public website. The backend suite covers authentication/enrollment, time windows, CSRF, sampling, scoring, deadline expiry, repeated submissions, session ownership, refresh/departure/disconnection locks, accommodations, retakes, private exports and immutable snapshots.
