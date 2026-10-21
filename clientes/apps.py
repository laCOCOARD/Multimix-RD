from django.apps import AppConfig


def recuperar_carrito(sender, request, user, **kwargs):
    """Al entrar, el carrito guardado en la cuenta vuelve a la sesion (aunque se entre desde otro equipo)."""
    if request is None or not hasattr(request, 'session'):
        return
    from carrito.carrito import recuperar_al_entrar

    recuperar_al_entrar(request, user)


class ClientesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clientes'
    verbose_name = 'Clientes'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        user_logged_in.connect(recuperar_carrito, dispatch_uid='clientes.recuperar_carrito')
