import json

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.safestring import mark_safe

from better_profanity import profanity
from .models import CustomUser, Question, Tag, Answer, Report
from .validators import validate_clean_content


# 1. ФОРМА ЗА РЕГИСТРАЦИЯ
class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        label="Потребителско име",
        min_length=3,
        max_length=20,
        help_text="Задължително. 3-20 символа.",
        validators=[validate_clean_content],
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control'})
    )
    email = forms.EmailField(
        label="Имейл",
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    # Checkbox за условията
    terms_confirmed = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=mark_safe(
            'Съгласен съм с <a href="/terms-of-service/" target="_blank" class="text-decoration-none">Условията за ползване</a>')
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'terms_confirmed')

    field_order = ['username', 'email', 'password1', 'password2', 'terms_confirmed']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['password1'].label = "Парола"
        self.fields['password2'].label = "Потвърди паролата"

        self.fields['username'].help_text = "3-20 символа. Уникално."
        self.fields['email'].help_text = "Въведете валиден имейл."

        self.fields['password1'].widget.attrs.update({'maxlength': '80'})
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({'maxlength': '80'})
            self.fields['password2'].help_text = "Повторете паролата."

        for field_name in self.fields:
            self.fields[field_name].error_messages['required'] = 'Това поле е задължително.'


# 2. РЕДАКЦИЯ НА ПРОФИЛ
class CustomUserChangeForm(UserChangeForm):
    password = None
    username = forms.CharField(
        min_length=3,
        max_length=20,
        help_text="3-20 символа. Уникално.",
        validators=[validate_clean_content],
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = CustomUser
        fields = ('username', 'email')


# 3. ПЕРСОНАЛИЗАЦИЯ
class PersonalizationForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('theme',)
        widgets = {
            'theme': forms.RadioSelect
        }


# 4. ВЪПРОСИ
class QuestionForm(forms.ModelForm):
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
        # Keep existing validators but we will also add clean methods
        self.fields['title'].validators.append(validate_clean_content)
        self.fields['content'].validators.append(validate_clean_content)

    def clean_title(self):
        title = self.cleaned_data['title']
        if profanity.contains_profanity(title):
            raise ValidationError("Заглавието съдържа нецензурни думи.")
        return title

    def clean_content(self):
        content = self.cleaned_data['content']
        if profanity.contains_profanity(content):
            raise ValidationError("Съдържанието съдържа нецензурни думи.")
        return content

    def clean_tags(self):
        tags_input = self.cleaned_data.get('tags', '')
        if not tags_input:
            return []

        # Parse the input – could be JSON from Tagify or a simple comma‑separated string
        try:
            tag_data = json.loads(tags_input)
            # Tagify sends a list of objects with a 'value' key
            if isinstance(tag_data, list):
                tag_names = [item['value'] for item in tag_data if 'value' in item]
            else:
                # fallback if it's not a list (shouldn't happen)
                tag_names = []
        except (json.JSONDecodeError, TypeError, KeyError):
            # Simple comma/space separated fallback
            tag_names = [t.strip() for t in tags_input.replace(',', ' ').split() if t.strip()]

        # Validate each tag name
        for name in tag_names:
            if profanity.contains_profanity(name):
                raise ValidationError(f"Тагът '{name}' съдържа нецензурни думи.")
            if len(name) > 50:
                raise ValidationError(f"Тагът '{name}' е твърде дълъг (макс. 50 символа).")

        return tag_names  # Return the clean list of tag names


# 5. ОТГОВОРИ
class AnswerForm(forms.ModelForm):
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
        content = self.cleaned_data['content']
        if profanity.contains_profanity(content):
            raise ValidationError("Отговорът съдържа нецензурни думи.")
        return content


# 6. ДОКЛАДИ
class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ('reason', 'description')
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Опишете проблема (макс. 150 символа)...',
                'maxlength': '150',
                'style': 'resize: none;'
            }),
        }

    def clean_description(self):
        description = self.cleaned_data['description']
        if profanity.contains_profanity(description):
            raise ValidationError("Описанието съдържа нецензурни думи.")
        return description
