from django.contrib.admin.apps import AdminConfig


class PanelAdminConfig(AdminConfig):
    """Reemplaza el sitio de administracion por el panel propio de la tienda."""
    default_site = 'core.admin_site.PanelAdminSite'
