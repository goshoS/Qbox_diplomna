from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('validate/registration/', views.validate_registration, name='validate_registration'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('login-success/', views.login_success, name='login_success'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('ask/', views.ask_question, name='ask_question'),
    path('vote/', views.vote, name='vote'),
    path('question/<int:pk>/', views.question_detail, name='question_detail'),
    path('question/<int:pk>/edit/', views.edit_question, name='edit_question'),
    path('question/<int:pk>/delete/', views.delete_question, name='delete_question'),

    # Път за създаване на доклад
    path('report/<str:obj_type>/<int:pk>/', views.create_report, name='create_report'),

    path('answer/<int:pk>/edit/', views.edit_answer, name='edit_answer'),
    path('answer/<int:pk>/delete/', views.delete_answer, name='delete_answer'),
    path('popular/', views.popular_questions, name='popular_questions'),
    path('recent/', views.recent_questions, name='recent_questions'),
    path('my-questions/', views.my_questions, name='my_questions'),
    path('liked/', views.liked_questions, name='liked_questions'),
    path('api/tags/', views.tag_list_api, name='tag_list_api'),

    # admin пътища

    path('manage/reports/', views.manage_reports, name='manage_reports'),
    path('manage/reports/<int:pk>/delete/', views.delete_report, name='delete_report'),

    path('manage/users/', views.manage_users, name='manage_users'),
    path('manage/users/<int:pk>/toggle-admin/', views.toggle_admin, name='toggle_admin'),
    path('manage/users/<int:pk>/delete/', views.delete_user, name='delete_user'),

    path('manage/questions/', views.manage_questions, name='manage_questions'),
    path('manage/questions/<int:pk>/delete/', views.admin_delete_question, name='admin_delete_question'),

    path('manage/tags/', views.manage_tags, name='manage_tags'),
    path('manage/tags/<int:pk>/delete/', views.delete_tag, name='delete_tag'),

    path('settings/', views.profile_settings, name='profile_settings'),
    path('settings/personalization/', views.personalization_settings, name='personalization_settings'),

    # legal
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
]
