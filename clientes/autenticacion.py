from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CorreoOUsuarioBackend(ModelBackend):
    """Entra con el nombre de usuario o con el correo de la cuenta.

    Los clientes usan el correo como nombre de usuario, pero el administrador y los vendedores tienen otro
    (MULTIMIX_ADMIN...). Sin esto, el formulario del sitio, que pide el correo, no los dejaba entrar. Solo vale
    si el correo es de una sola cuenta.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        usuario = super().authenticate(request, username=username, password=password, **kwargs)
        if usuario is not None or not username or '@' not in username or password is None:
            return usuario
        cuentas = list(get_user_model()._default_manager.filter(email__iexact=username.strip())[:2])
        if len(cuentas) != 1:
            # Igual se calcula una contraseña, para no revelar por el tiempo si el correo existe.
            get_user_model()().set_password(password)
            return None
        cuenta = cuentas[0]
        if cuenta.check_password(password) and self.user_can_authenticate(cuenta):
            return cuenta
        return None
