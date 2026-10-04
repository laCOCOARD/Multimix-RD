from django.contrib import admin


class PanelAdminSite(admin.AdminSite):
    site_header = 'Multimix RD'
    site_title = 'Panel Multimix RD'
    index_title = 'Resumen de la tienda'
    site_url = '/'

    def index(self, request, extra_context=None):
        from .panel import resumen_panel  # se importa aqui: los modelos aun no existen al crear el sitio

        contexto = {'resumen': resumen_panel()} if request.user.has_perm('pedidos.view_pedido') else {}
        contexto.update(extra_context or {})
        return super().index(request, extra_context=contexto)
