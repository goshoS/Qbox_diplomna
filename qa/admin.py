from django.contrib import admin
from .models import CustomUser, Question, Tag, Answer

admin.site.register(CustomUser)
admin.site.register(Question)
admin.site.register(Tag)
admin.site.register(Answer)