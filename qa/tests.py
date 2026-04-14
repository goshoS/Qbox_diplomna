import json
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import Question, Answer, Tag, Report
from .validators import validate_clean_content, MaximumLengthValidator
from .forms import QuestionForm

User = get_user_model()


class ValidatorTests(TestCase):
    """ Тестове за къстъм валидаторите (Сигурност и филтриране) """

    def test_maximum_length_validator(self):
        validator = MaximumLengthValidator(max_length=10)
        # Валидна парола
        self.assertIsNone(validator.validate("Short123!"))
        # Невалидна парола (над 10 символа)
        with self.assertRaises(ValidationError):
            validator.validate("ThisPasswordIsTooLong123!")

    def test_profanity_validator_clean_text(self):
        # Чист текст трябва да минава без грешка
        self.assertIsNone(validate_clean_content("Това е нормален въпрос."))

    def test_profanity_validator_bad_text(self):
        # Текст с нецензурна дума (от BG_BAD_WORDS списък) трябва да хвърля грешка
        with self.assertRaises(ValidationError):
            validate_clean_content("Ти си тъпак")


class ModelTests(TestCase):
    """ Тестове за логиката на базата данни (Моделите) """

    def setUp(self):
        # Създаваме тестов потребител
        self.user = User.objects.create_user(username='testuser', email='test@abv.bg', password='Password123!')

    def test_tag_slug_generation(self):
        # Проверяваме дали кирилицата се запазва правилно в slug-а
        tag = Tag.objects.create(name='Програмиране')
        self.assertEqual(tag.slug, 'програмиране')

    def test_question_likes_counting(self):
        question = Question.objects.create(author=self.user, title='Тест', content='Съдържание')
        # Първоначално трябва да е 0
        self.assertEqual(question.total_likes(), 0)

        # Добавяме лайк
        question.likes.add(self.user)
        self.assertEqual(question.total_likes(), 1)


class FormTests(TestCase):
    """ Тестове за валидацията на формите """

    def test_question_form_valid(self):
        form_data = {
            'title': 'Как да инсталирам Django?',
            'content': 'Имам нужда от помощ с инсталацията на локален сървър.',
            'tags': '[{"value":"django"}, {"value":"python"}]'  # Симулираме Tagify JSON
        }
        form = QuestionForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_question_form_profanity_invalid(self):
        form_data = {
            'title': 'Някакво тъпак заглавие',  # 'тъпак' е в списъка с нецензурни думи
            'content': 'Нормално съдържание',
        }
        form = QuestionForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)


class ViewAccessTests(TestCase):
    """ Тестове за права на достъп (Оторизация) и рендиране на страници """

    def setUp(self):
        self.client = Client()
        self.guest = User.objects.create_user(username='guest_user', email='guest@test.com', password='pwd')
        self.admin = User.objects.create_user(username='admin_user', email='admin@test.com', password='pwd',
                                              is_admin=True)
        self.superadmin = User.objects.create_superuser(username='super', email='super@test.com', password='pwd')

        self.question = Question.objects.create(author=self.guest, title='Q1', content='C1')

    def test_home_page_status(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_ask_question_requires_login(self):
        # Гост се опитва да отвори страницата за задаване на въпрос
        response = self.client.get(reverse('ask_question'))

        # Трябва да бъде пренасочен (302) към страницата за вход
        self.assertEqual(response.status_code, 302)

        # Взимаме точния адрес на логин страницата (за да е гъвкав тестът)
        login_url = reverse('login')
        self.assertTrue(response.url.startswith(login_url))

    def test_manage_users_admin_access(self):
        # 1. Обикновен потребител (Грешка 403 Forbidden)
        self.client.force_login(self.guest)
        response_guest = self.client.get(reverse('manage_users'))
        self.assertEqual(response_guest.status_code, 403)

        # 2. Админ (Успех 200 OK)
        self.client.force_login(self.admin)
        response_admin = self.client.get(reverse('manage_users'))
        self.assertEqual(response_admin.status_code, 200)


class AjaxVoteTests(TestCase):
    """ Тестове за AJAX функционалността за гласуване """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='voter', email='voter@test.com', password='pwd')
        self.question = Question.objects.create(author=self.user, title='Test Vote', content='Vote Content')

    def test_vote_like_toggle(self):
        self.client.force_login(self.user)

        payload = {'type': 'question', 'id': self.question.id, 'action': 'like'}

        # 1. Първо натискане (Харесва)
        response = self.client.post(
            reverse('vote'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['user_liked'])
        self.assertEqual(data['total_likes'], 1)

        # 2. Второ натискане на същия бутон (Премахва харесването)
        response2 = self.client.post(
            reverse('vote'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        data2 = response2.json()
        self.assertFalse(data2['user_liked'])
        self.assertEqual(data2['total_likes'], 0)
