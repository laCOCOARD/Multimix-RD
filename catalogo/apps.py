from django.apps import AppConfig


class CatalogoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalogo'

    def ready(self):
        from . import avisos  # noqa: F401  (conecta el aviso de "ya esta disponible")
