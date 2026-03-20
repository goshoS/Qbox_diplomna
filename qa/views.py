import re
import json

from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Count, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from better_profanity import profanity
from .validators import BG_BAD_WORDS, validate_clean_content
from .forms import (
    CustomUserCreationForm, QuestionForm, AnswerForm,
    CustomUserChangeForm, PersonalizationForm, ReportForm
)
from .models import CustomUser, Question, Tag, Answer, Report
from .decorators import admin_required, superuser_required


# --- Helper функция за лявото меню ---
def get_popular_tags():
    return Tag.objects.annotate(num_questions=Count('questions')).order_by('-num_questions')[:5]


# --- API за Tagify ---
def tag_list_api(request):
    tags = list(Tag.objects.values_list('name', flat=True))
    return JsonResponse(tags, safe=False)


# --- Views ---

def home(request):
    query = request.GET.get('q')
    questions = Question.objects.select_related('author').prefetch_related('tags', 'likes', 'dislikes').order_by(
        '-created_at')

    if query:
        questions = questions.filter(
            Q(title__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

    context = {'questions': questions, 'query': query, 'popular_tags': get_popular_tags()}

    # Проверка за AJAX
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'includes/question_list.html', context)

    return render(request, 'home.html', context)


def popular_questions(request):
    questions = Question.objects.annotate(
        num_likes=Count('likes', distinct=True),
        num_dislikes=Count('dislikes', distinct=True)
    ).annotate(
        score=F('num_likes') - F('num_dislikes')
    ).select_related('author').prefetch_related('tags', 'likes', 'dislikes').order_by('-score', '-created_at')

    context = {'questions': questions, 'popular_tags': get_popular_tags()}
    return render(request, 'home.html', context)


def recent_questions(request):
    questions = Question.objects.select_related('author').prefetch_related('tags', 'likes', 'dislikes').order_by(
        '-created_at')

    context = {'questions': questions, 'popular_tags': get_popular_tags()}
    return render(request, 'home.html', context)


@login_required
def my_questions(request):
    questions = Question.objects.filter(author=request.user).select_related('author').prefetch_related('tags', 'likes',
                                                                                                       'dislikes').order_by(
        '-created_at')

    context = {'questions': questions, 'popular_tags': get_popular_tags()}
    return render(request, 'home.html', context)


@login_required
def liked_questions(request):
    questions = Question.objects.filter(likes=request.user).select_related('author').prefetch_related('tags', 'likes',
                                                                                                      'dislikes').order_by(
        '-created_at')

    context = {'questions': questions, 'popular_tags': get_popular_tags()}
    return render(request, 'home.html', context)


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def login_success(request):
    """
    Тази функция проверява ролята на потребителя след вход
    и го препраща към съответната начална страница.
    """
    if request.user.is_superuser or request.user.is_admin:
        return redirect('manage_users')  # Админите отиват в панела
    else:
        return redirect('home')  # Обикновените потребители отиват в Home


@login_required
def ask_question(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.author = request.user
            question.save()

            # Добавяне на тагове – tags вече е списък от имена (почистен и валидиран)
            for tag_name in form.cleaned_data['tags']:
                tag, _ = Tag.objects.get_or_create(name=tag_name.lower())
                question.tags.add(tag)

            if request.user.is_admin or request.user.is_superuser:
                return redirect('manage_questions')
            else:
                return redirect('home')
    else:
        form = QuestionForm()

    return render(request, 'ask_question.html', {'form': form, 'popular_tags': get_popular_tags()})


@login_required
@require_POST
def vote(request):
    data = json.loads(request.body)
    obj_type = data.get('type')
    obj_id = data.get('id')
    action = data.get('action')

    if obj_type == 'question':
        obj = get_object_or_404(Question, pk=obj_id)
    elif obj_type == 'answer':
        obj = get_object_or_404(Answer, pk=obj_id)
    else:
        return JsonResponse({'error': 'Invalid type'}, status=400)

    user = request.user

    if action == 'like':
        if user in obj.likes.all():
            obj.likes.remove(user)
        else:
            if user in obj.dislikes.all():
                obj.dislikes.remove(user)
            obj.likes.add(user)

    elif action == 'dislike':
        if user in obj.dislikes.all():
            obj.dislikes.remove(user)
        else:
            if user in obj.likes.all():
                obj.likes.remove(user)
            obj.dislikes.add(user)

    return JsonResponse({
        'total_likes': obj.total_likes(),
        'total_dislikes': obj.total_dislikes(),
        'user_liked': user in obj.likes.all(),
        'user_disliked': user in obj.dislikes.all()
    })


def question_detail(request, pk):
    question = get_object_or_404(
        Question.objects.select_related('author').prefetch_related('tags', 'likes', 'dislikes'),
        pk=pk
    )
    answers = question.answers.select_related('author').prefetch_related('likes', 'dislikes').order_by('-created_at')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')

        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.author = request.user
            answer.question = question
            answer.save()
            return redirect('question_detail', pk=pk)
    else:
        form = AnswerForm()

    context = {
        'question': question,
        'answers': answers,
        'form': form,
        'popular_tags': get_popular_tags()
    }
    return render(request, 'question_detail.html', context)


# --- РЕДАКЦИЯ И ИЗТРИВАНЕ (USER) ---

@login_required
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk)

    if request.user != question.author:
        return HttpResponseForbidden("Нямате права да редактирате този въпрос.")

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            question = form.save(commit=False)
            question.save()

            # Обновяване на таговете
            question.tags.clear()
            for tag_name in form.cleaned_data['tags']:
                tag, _ = Tag.objects.get_or_create(name=tag_name.lower())
                question.tags.add(tag)

            return redirect('question_detail', pk=question.pk)
    else:
        # Подготвяме началните тагове като JSON за Tagify
        tags_list = [tag.name for tag in question.tags.all()]
        initial_tags = json.dumps([{'value': name} for name in tags_list])
        form = QuestionForm(instance=question, initial={'tags': initial_tags})

    return render(request, 'edit_question.html', {
        'form': form,
        'question': question,
        'popular_tags': get_popular_tags()
    })


@login_required
def delete_question(request, pk):
    question = get_object_or_404(Question, pk=pk)

    # Проверяваме дали e автор, админ или суперадмин
    is_authorized = (request.user == question.author) or request.user.is_admin or request.user.is_superuser

    if not is_authorized:
        return HttpResponseForbidden("Нямате права да изтриете този въпрос.")

    if request.method == 'POST':
        question.delete()

        # Проверяваме кой трие въпроса и го пращаме на правилното място
        if request.user.is_admin or request.user.is_superuser:
            return redirect('manage_reports')
        else:
            return redirect('home')

    return render(request, 'delete_confirm.html', {
        'object': question,
        'type': 'question',
        'popular_tags': get_popular_tags()
    })


@login_required
def edit_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)

    if request.user != answer.author:
        return HttpResponseForbidden("Нямате права да редактирате този отговор.")

    if request.method == 'POST':
        form = AnswerForm(request.POST, instance=answer)
        if form.is_valid():
            form.save()
            return redirect('question_detail', pk=answer.question.pk)
    else:
        form = AnswerForm(instance=answer)

    return render(request, 'edit_answer.html', {
        'form': form,
        'answer': answer,
    })


@login_required
def delete_answer(request, pk):
    answer = get_object_or_404(Answer, pk=pk)
    question_pk = answer.question.pk

    is_authorized = (request.user == answer.author) or (request.user.is_admin) or (request.user.is_superuser)

    if not is_authorized:
        return HttpResponseForbidden("Нямате права да изтриете този отговор.")

    if request.method == 'POST':
        answer.delete()
        return redirect('question_detail', pk=question_pk)

    return render(request, 'delete_confirm.html', {
        'object': answer,
        'type': 'answer',
    })


# --- АДМИНИСТРАТИВЕН ПАНЕЛ ---

@admin_required
def manage_users(request):
    query = request.GET.get('q')
    users = CustomUser.objects.all().order_by('id')

    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))

    context = {'users': users, 'query': query}

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'includes/admin_users_list.html', context)

    return render(request, 'admin/manage_users.html', context)


@superuser_required
def toggle_admin(request, pk):
    user_to_edit = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        user_to_edit.is_admin = not user_to_edit.is_admin
        user_to_edit.save()
    return redirect('manage_users')


@admin_required
def delete_user(request, pk):
    user_to_delete = get_object_or_404(CustomUser, pk=pk)

    if user_to_delete.is_superuser:
        return HttpResponseForbidden("Не може да изтриете SuperAdmin.")

    if request.user == user_to_delete:
        return HttpResponseForbidden("Не може да изтриете собствения си акаунт докато сте влезли в него.")

    if request.method == 'POST':
        confirmation = request.POST.get('confirmation_text')

        if confirmation == user_to_delete.username:
            user_to_delete.delete()
            return redirect('manage_users')
        else:
            return render(request, 'delete_confirm.html', {
                'object': user_to_delete,
                'type': 'user',
                'error': 'Въведеното име не съвпада! Опитайте отново.'
            })

    return render(request, 'delete_confirm.html', {
        'object': user_to_delete,
        'type': 'user',
    })


@admin_required
def manage_questions(request):
    query = request.GET.get('q')
    questions = Question.objects.select_related('author').prefetch_related('tags', 'likes', 'dislikes').order_by(
        '-created_at')

    if query:
        questions = questions.filter(Q(title__icontains=query) | Q(content__icontains=query))

    context = {'questions': questions, 'query': query}

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'includes/admin_questions_list.html', context)

    return render(request, 'admin/manage_questions.html', context)


@admin_required
def admin_delete_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        question.delete()
        return redirect('manage_questions')

    return render(request, 'delete_confirm.html', {
        'object': question,
        'type': 'question',
    })


@admin_required
def manage_tags(request):
    query = request.GET.get('q')
    tags = Tag.objects.annotate(count=Count('questions')).order_by('-count')

    if query:
        tags = tags.filter(name__icontains=query)

    context = {'tags': tags, 'query': query}

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'includes/admin_tags_list.html', context)

    return render(request, 'admin/manage_tags.html', context)


@admin_required
def delete_tag(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    if request.method == 'POST':
        tag.delete()
        return redirect('manage_tags')

    return render(request, 'delete_confirm.html', {
        'object': tag,
        'type': 'tag',
    })


def validate_registration(request):
    """Проверява полетата в реално време"""
    if request.method == 'POST':
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')

        response = {
            'is_valid': True,
            'error_msg': ''
        }

        # Глобална проверка за нецензурни думи преди всичко друго
        if value and profanity.contains_profanity(value):
            return JsonResponse({
                'is_valid': False,
                'error_msg': 'Нецензурният език е забранен.'
            })

        # 1. Username
        if field == 'username':
            if not value:
                response['is_valid'] = False
                response['error_msg'] = 'Потребителското име е задължително.'
            elif len(value) < 3:
                response['is_valid'] = False
                response['error_msg'] = 'Името трябва да е поне 3 символа.'
            elif len(value) > 20:
                response['is_valid'] = False
                response['error_msg'] = 'Името не може да е над 20 символа.'
            elif CustomUser.objects.filter(username__iexact=value).exists():
                response['is_valid'] = False
                response['error_msg'] = 'Това потребителско име е заето.'

        # 2. Email
        elif field == 'email':
            if not value:
                response['is_valid'] = False
                response['error_msg'] = 'Имейлът е задължителен.'
            else:
                try:
                    validate_email(value)
                    if CustomUser.objects.filter(email__iexact=value).exists():
                        response['is_valid'] = False
                        response['error_msg'] = 'Този имейл вече е регистриран.'
                except ValidationError:
                    response['is_valid'] = False
                    response['error_msg'] = 'Въведете валиден имейл адрес.'

        # 3. Парола
        elif field == 'password':
            if not value or len(value) < 8:
                response['is_valid'] = False
                response['error_msg'] = 'Паролата трябва да е минимум 8 символа'
            elif not re.search(r'[A-Z]', value):
                response['is_valid'] = False
                response['error_msg'] = 'Паролата трябва да съдържа поне една главна буква'
            elif not re.search(r'[0-9]', value):
                response['is_valid'] = False
                response['error_msg'] = 'Паролата трябва да съдържа поне едно число'
            elif not re.search(r'[^A-Za-z0-9]', value):
                response['is_valid'] = False
                response['error_msg'] = 'Паролата трябва да съдържа поне един специален символ'

        return JsonResponse(response)

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def profile_settings(request):
    user_instance = get_object_or_404(CustomUser, pk=request.user.pk)

    profile_form = CustomUserChangeForm(instance=user_instance)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = CustomUserChangeForm(request.POST, instance=user_instance)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профилът ви беше обновен успешно!')
                return redirect('profile_settings')

        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Паролата ви беше променена успешно!')
                return redirect('profile_settings')

    return render(request, 'settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'popular_tags': get_popular_tags()
    })


@login_required
def personalization_settings(request):
    user = request.user

    if request.method == 'POST':
        form = PersonalizationForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('personalization_settings')
    else:
        form = PersonalizationForm(instance=user)

    return render(request, 'personalization.html', {'form': form, 'popular_tags': get_popular_tags()})


@login_required
def create_report(request, obj_type, pk):
    question_obj = None
    answer_obj = None

    if obj_type == 'question':
        question_obj = get_object_or_404(Question, pk=pk)
    elif obj_type == 'answer':
        answer_obj = get_object_or_404(Answer, pk=pk)
    else:
        return redirect('home')

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.question = question_obj
            report.answer = answer_obj
            report.save()

            if question_obj:
                return redirect('question_detail', pk=question_obj.pk)
            else:
                return redirect('question_detail', pk=answer_obj.question.pk)
    else:
        form = ReportForm()

    return render(request, 'report_create.html', {
        'form': form,
        'obj_type': obj_type,
        'popular_tags': get_popular_tags()
    })


# --- АДМИН ПАНЕЛ ЗА ДОКЛАДИ ---

@admin_required
def manage_reports(request):
    reports = Report.objects.select_related('reporter', 'question', 'answer', 'question__author',
                                            'answer__author').order_by('-created_at')

    return render(request, 'admin/manage_reports.html', {'reports': reports})


@admin_required
def delete_report(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if request.method == 'POST':
        report.delete()
        return redirect('manage_reports')

    return render(request, 'delete_confirm.html', {
        'object': report,
        'type': 'report',
    })


def privacy_policy(request):
    return render(request, 'legal/privacy_policy.html', {'popular_tags': get_popular_tags()})


def terms_of_service(request):
    return render(request, 'legal/terms_of_service.html', {'popular_tags': get_popular_tags()})
