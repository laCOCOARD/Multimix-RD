from django.apps import AppConfig
from django.db.models.signals import post_migrate


class TiendasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tiendas'
    verbose_name = 'Tiendas'

    def ready(self):
        from .services import preparar_grupo_vendedores

        post_migrate.connect(preparar_grupo_vendedores, sender=self)
