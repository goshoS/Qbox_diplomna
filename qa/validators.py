from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from better_profanity import profanity

# --- КОНФИГУРАЦИЯ ЗА НЕЦЕНЗУРНИ ДУМИ ---

profanity.load_censor_words()

BG_BAD_WORDS = [
    'глупак', 'идиот', 'простак', 'тъпак', 'майка ти дейба', 'педал', 'копеле',
    'кур', 'пенис', 'путка', 'путак', 'пичка', 'травестит', 'шибан', 'шибаняк',
    'еба', 'секс', 'задник', 'курва', 'кучка', 'педераст', 'негър', 'ретард', 'лайно'
]

# Добавям ги към общия списък
profanity.add_censor_words(BG_BAD_WORDS)

def validate_clean_content(value):
    """
    Проверява дали текстът съдържа нецензурни думи (EN + BG).
    Хвърля грешка, ако намери такива.
    """
    if not value:
        return

    # contains_profanity връща True, ако намери лоша дума
    if profanity.contains_profanity(value):
        raise ValidationError(
            _("Съдържанието съдържа нецензурен език. Моля, бъдете учтиви."),
            code='profanity_detected'
        )

# --- ВАЛИДАТОР ЗА ПАРОЛА
class MaximumLengthValidator:
    def __init__(self, max_length=80):
        self.max_length = max_length

    def validate(self, password, user=None):
        if len(password) > self.max_length:
            raise ValidationError(
                _("Паролата е твърде дълга. Максимумът е %(max_length)d символа."),
                code='password_too_long',
                params={'max_length': self.max_length},
            )

    def get_help_text(self):
        return _(
            "Паролата трябва да бъде най-много %(max_length)d символа."
        ) % {'max_length': self.max_length}