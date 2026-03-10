import json

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.safestring import mark_safe

from better_profanity import profanity
from .models import CustomUser, Question, Tag, Answer, Report
from .validators import validate_clean_content


# ======================================================================
# 1. ФОРМА ЗА РЕГИСТРАЦИЯ НА ПОТРЕБИТЕЛ
# ======================================================================
class CustomUserCreationForm(UserCreationForm):
    """
    Разширява стандартната форма за регистрация на Django (UserCreationForm),
    за да работи с нашия персонализиран модел CustomUser.
    Добавя допълнителни полета (имейл, съгласие с условията) и валидации.
    """
    username = forms.CharField(
        label="Потребителско име",
        min_length=3,
        max_length=20,
        help_text="Задължително. 3-20 символа.",
        validators=[validate_clean_content],  # Проверка за нецензурно съдържание
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control'})
    )
    email = forms.EmailField(
        label="Имейл",
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    # Поле за съгласие с общите условия – задължително отметка
    terms_confirmed = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=mark_safe(
            'Съгласен съм с <a href="/terms-of-service/" target="_blank" class="text-decoration-none">Условията за ползване</a>')
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'terms_confirmed')  # Кои полета да се показват

    # Ред на полетата (за да са password1 и password2 след имейла)
    field_order = ['username', 'email', 'password1', 'password2', 'terms_confirmed']

    def __init__(self, *args, **kwargs):
        """Настройва етикети, помощни текстове и атрибути на полетата за пароли."""
        super().__init__(*args, **kwargs)

        self.fields['password1'].label = "Парола"
        self.fields['password2'].label = "Потвърди паролата"

        self.fields['username'].help_text = "3-20 символа. Уникално."
        self.fields['email'].help_text = "Въведете валиден имейл."

        # Ограничаване на дължината на паролите (за съвместимост с модела)
        self.fields['password1'].widget.attrs.update({'maxlength': '80'})
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({'maxlength': '80'})
            self.fields['password2'].help_text = "Повторете паролата."

        # Заместване на стандартните съобщения за грешка „празно поле“
        for field_name in self.fields:
            self.fields[field_name].error_messages['required'] = 'Това поле е задължително.'


# ======================================================================
# 2. ФОРМА ЗА РЕДАКТИРАНЕ НА ПРОФИЛ
# ======================================================================
class CustomUserChangeForm(UserChangeForm):
    """
    Форма за промяна на потребителските данни (потребителско име и имейл).
    Премахва полето за парола от наследената форма, за да не се показва.
    """
    password = None  # Скрива полето за парола от UserChangeForm

    username = forms.CharField(
        min_length=3,
        max_length=20,
        help_text="3-20 символа. Уникално.",
        validators=[validate_clean_content],
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email')


# ======================================================================
# 3. ФОРМА ЗА ПЕРСОНАЛИЗАЦИЯ (ТЕМА)
# ======================================================================
class PersonalizationForm(forms.ModelForm):
    """
    Форма за промяна на темата на интерфейса (светла/тъмна).
    Използва radio бутони за избор.
    """

    class Meta:
        model = CustomUser
        fields = ('theme',)
        widgets = {
            'theme': forms.RadioSelect  # Показва опциите като радио бутони
        }


# ======================================================================
# 4. ФОРМА ЗА СЪЗДАВАНЕ/РЕДАКТИРАНЕ НА ВЪПРОС
# ======================================================================
class QuestionForm(forms.ModelForm):
    """
    Форма за въпрос. Включва поле за тагове (текстово поле, което може да приема
    JSON от библиотека Tagify или обикновен списък с разделители).
    Валидира за нецензурно съдържание в заглавието, съдържанието и таговете.
    """
    tags = forms.CharField(
        required=False,
        validators=[validate_clean_content],
        widget=forms.TextInput(attrs={'placeholder': 'Тагове...', 'class': 'form-control'})
    )

    class Meta:
        model = Question
        fields = ('title', 'content', 'tags')
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Какво искаш да попиташ?',
                'class': 'form-control'
            }),
            'content': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Опиши проблема си детайлно...',
                'maxlength': '5000',
                'class': 'form-control',
                'style': 'resize: vertical; max-height: 500px;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавяне на валидатор за нецензурно съдържание към полетата title и content
        self.fields['title'].validators.append(validate_clean_content)
        self.fields['content'].validators.append(validate_clean_content)

    def clean_title(self):
        """Заглавието не трябва да съдържа нецензурни думи."""
        title = self.cleaned_data['title']
        if profanity.contains_profanity(title):
            raise ValidationError("Заглавието съдържа нецензурни думи.")
        return title

    def clean_content(self):
        """Съдържанието не трябва да съдържа нецензурни думи."""
        content = self.cleaned_data['content']
        if profanity.contains_profanity(content):
            raise ValidationError("Съдържанието съдържа нецензурни думи.")
        return content

    def clean_tags(self):
        """
        Обработва въведените тагове. Поддържа два формата:
         - JSON от Tagify (списък от обекти с ключ 'value')
         - обикновен текст, разделен със запетая или интервал.
        Връща списък от имена на тагове, след като ги е валидирал (нецензурно, дължина).
        """
        tags_input = self.cleaned_data.get('tags', '')
        if not tags_input:
            return []

        # Опит за парсване като JSON (Tagify)
        try:
            tag_data = json.loads(tags_input)
            if isinstance(tag_data, list):
                tag_names = [item['value'] for item in tag_data if 'value' in item]
            else:
                tag_names = []
        except (json.JSONDecodeError, TypeError, KeyError):
            # Ако не е JSON – разцепва по запетая/интервал
            tag_names = [t.strip() for t in tags_input.replace(',', ' ').split() if t.strip()]

        # Валидация на всяко име на таг
        for name in tag_names:
            if profanity.contains_profanity(name):
                raise ValidationError(f"Тагът '{name}' съдържа нецензурни думи.")
            if len(name) > 50:
                raise ValidationError(f"Тагът '{name}' е твърде дълъг (макс. 50 символа).")

        return tag_names  # Връща списък от имена (ще се използва във view за създаване/свързване на обекти Tag)


# ======================================================================
# 5. ФОРМА ЗА ОТГОВОР
# ======================================================================
class AnswerForm(forms.ModelForm):
    """
    Форма за добавяне или редактиране на отговор към въпрос.
    Валидира съдържанието за нецензурни думи.
    """

    class Meta:
        model = Answer
        fields = ('content',)
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Напиши своя отговор тук...',
                'class': 'form-control',
                'style': 'resize: vertical; max-height: 400px;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].validators.append(validate_clean_content)

    def clean_content(self):
        """Отговорът не трябва да съдържа нецензурни думи."""
        content = self.cleaned_data['content']
        if profanity.contains_profanity(content):
            raise ValidationError("Отговорът съдържа нецензурни думи.")
        return content


# ======================================================================
# 6. ФОРМА ЗА ДОКЛАДВАНЕ (РЕПОРТ)
# ======================================================================
class ReportForm(forms.ModelForm):
    """
    Форма за подаване на сигнал за неподходящо съдържание (въпрос, отговор и др.).
    Включва причина (избира се от списък) и описание.
    """

    class Meta:
        model = Report
        fields = ('reason', 'description')
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),  # Падащо меню
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опишете проблема (макс. 150 символа)...',
                'maxlength': '150',
                'style': 'resize: none;'  # Забранява промяна на размера
            }),
        }

    def clean_description(self):
        """Описанието не трябва да съдържа нецензурни думи."""
        description = self.cleaned_data['description']
        if profanity.contains_profanity(description):
            raise ValidationError("Описанието съдържа нецензурни думи.")
        return description
