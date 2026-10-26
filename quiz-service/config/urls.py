from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from assessment import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.StudentLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', views.lobby, name='lobby'),
    path('quiz/<int:quiz_id>/', views.quiz_page, name='quiz'),
    path('api/quiz/<int:quiz_id>/start/', views.start_attempt, name='start'),
    path('api/attempt/<int:attempt_id>/<str:action>/', views.attempt_action, name='action'),
    path('instructor/', views.instructor, name='instructor'),
    path('instructor/<int:quiz_id>/results.csv', views.export_results, name='export'),
]
