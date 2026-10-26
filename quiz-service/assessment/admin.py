from django.contrib import admin, messages
from django.db import transaction
from .models import Question, Quiz, Enrollment, Attempt, AuditEvent


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('code', 'topic', 'active')
    list_filter = ('topic', 'active')
    search_fields = ('code', 'prompt')


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = ('student',)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'opens_at', 'closes_at', 'seconds_per_question', 'published')
    filter_horizontal = ('questions',)
    inlines = [EnrollmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'seconds_override')
    list_filter = ('quiz',)
    autocomplete_fields = ('student',)


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'enrollment', 'status', 'score', 'started_at', 'reason')
    list_filter = ('status', 'enrollment__quiz')
    readonly_fields = tuple(field.name for field in Attempt._meta.fields)
    actions = ['authorize_retake']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Authorize a fresh attempt for selected LOCKED attempts (retain audit trail)', permissions=['change'])
    def authorize_retake(self, request, queryset):
        count = 0
        with transaction.atomic():
            for attempt in queryset.select_for_update().filter(status='locked'):
                attempt.status = 'void'
                attempt.save(update_fields=['status'])
                AuditEvent.objects.create(attempt=attempt, actor=request.user, event='Instructor authorized fresh attempt')
                count += 1
        self.message_user(request, f'{count} locked attempt(s) voided; students may start again within the access window.', messages.SUCCESS)


@admin.register(AuditEvent)
class AuditAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'at', 'event', 'actor')
    readonly_fields = ('attempt', 'at', 'event', 'actor')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
