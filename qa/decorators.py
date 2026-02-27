from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required

def admin_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Разрешаваме достъп ако е Admin ИЛИ SuperUser
        if request.user.is_admin or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Нямате административни права.")
    return _wrapped_view

def superuser_required(view_func):
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Само SuperAdmin може да прави това.")
    return _wrapped_view