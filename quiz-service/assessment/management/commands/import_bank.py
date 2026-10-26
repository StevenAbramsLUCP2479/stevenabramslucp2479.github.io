import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from assessment.models import Question


class Command(BaseCommand):
    help = 'Import exactly 100 questions from a JSON file (private file supported). Does not publish a quiz.'

    def add_arguments(self, parser):
        parser.add_argument('path')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            with open(options['path'], encoding='utf-8') as source:
                bank = json.load(source)
            if not isinstance(bank, list) or len(bank) != 100 or len({q['code'] for q in bank}) != 100:
                raise ValueError('Expected exactly 100 questions with unique codes.')
            for row in bank:
                question = Question.objects.filter(code=row['code']).first() or Question(code=row['code'])
                for field in ('topic', 'prompt', 'options', 'correct', 'explanation'):
                    setattr(question, field, row[field])
                question.full_clean()
                question.save()
        except Exception as exc:
            raise CommandError(f'Bank rejected; no changes saved: {exc}') from exc
        self.stdout.write(self.style.SUCCESS('Imported 100 questions.'))
