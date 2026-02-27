from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify


class CustomUser(AbstractUser):
    # имейла е уникален и задължителен
    email = models.EmailField(unique=True, blank=False)

    THEME_CHOICES = [
        ('light', 'Light Mode'),
        ('dark', 'Dark Mode'),
    ]
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')

    is_admin = models.BooleanField(default=False)

    # Добавяме това, за да може Django да търси по email при нужда,
    # но username си остава основен за вход
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username


# 2. Модел за Тагове
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, allow_unicode=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# 3. Модел за Въпроси
class Question(models.Model):
    author = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='questions')

    title = models.CharField(max_length=255)
    content = models.TextField()
    tags = models.ManyToManyField(Tag, related_name='questions', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    likes = models.ManyToManyField(CustomUser, related_name='liked_questions', blank=True)
    dislikes = models.ManyToManyField(CustomUser, related_name='disliked_questions', blank=True)

    def total_likes(self):
        return self.likes.count()

    def total_dislikes(self):
        return self.dislikes.count()

    def __str__(self):
        return self.title


# 4. Модел за Отговори
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')

    author = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='answers')

    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    likes = models.ManyToManyField(CustomUser, related_name='liked_answers', blank=True)
    dislikes = models.ManyToManyField(CustomUser, related_name='disliked_answers', blank=True)

    def total_likes(self):
        return self.likes.count()

    def total_dislikes(self):
        return self.dislikes.count()

    def __str__(self):
        author_name = self.author.username if self.author else "Deleted User"
        return f"Answer by {author_name} on {self.question.title}"


class Report(models.Model):
    REPORT_REASONS = [
        ('spam', 'Спам или реклама'),
        ('abuse', 'Обиден език или тормоз'),
        ('irrelevant', 'Не е по темата'),
        ('other', 'Друго'),
    ]

    reporter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reports_sent')

    # Може да се докладва или въпрос, или отговор
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')

    reason = models.CharField(max_length=20, choices=REPORT_REASONS, default='spam')
    description = models.TextField(blank=True, help_text="Допълнителна информация (по желание)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report by {self.reporter.username}"
