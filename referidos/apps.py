from django.apps import AppConfig


class ReferidosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'referidos'
    verbose_name = 'Referidos'

    def ready(self):
        from django.db.models.signals import m2m_changed

        def _usuarios_cambiaron(sender, instance, action, pk_set, **kwargs):
            if action != 'post_add' or not pk_set:
                return
            from django.contrib.auth import get_user_model
            from .services import marcar_tienda_creada
            User = get_user_model()
            for pk in pk_set:
                try:
                    marcar_tienda_creada(User.objects.get(pk=pk))
                except User.DoesNotExist:
                    pass

        from tiendas.models import Tienda
        m2m_changed.connect(_usuarios_cambiaron, sender=Tienda.usuarios.through)
