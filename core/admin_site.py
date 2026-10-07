from django.contrib import admin


class PanelAdminSite(admin.AdminSite):
    site_header = 'Multimix RD'
    site_title = 'Panel Multimix RD'
    index_title = 'Resumen del sitio'
    site_url = '/'

    def index(self, request, extra_context=None):
        # Se importa aqui: los modelos aun no existen al crear el sitio.
        from tiendas.panel import tiendas_del_panel
        from tiendas.services import ve_todas

        from .panel import resumen_panel, ventas_por_tienda

        contexto = {}
        if request.user.has_perm('pedidos.view_pedido'):
            if ve_todas(request.user):
                # El administrador principal ve el total del sitio y el desglose por tienda.
                contexto = {'resumen': resumen_panel(), 'ventas_por_tienda': ventas_por_tienda()}
            else:
                tiendas = tiendas_del_panel(request)
                contexto = {
                    'resumen': resumen_panel(tiendas),
                    'title': 'Resumen de ' + (', '.join(tienda.nombre for tienda in tiendas) or 'tu tienda'),
                }
        contexto.update(extra_context or {})
        return super().index(request, extra_context=contexto)
