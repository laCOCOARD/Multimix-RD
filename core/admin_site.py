from django.contrib import admin

from clientes.forms import EntrarAlPanelForm


class PanelAdminSite(admin.AdminSite):
    site_header = 'Multimix RD'
    site_title = 'Panel Multimix RD'
    index_title = 'Resumen del sitio'
    site_url = '/'
    # Con limite de intentos: la pantalla de Django no lo trae.
    login_form = EntrarAlPanelForm

    def index(self, request, extra_context=None):
        # Se importa aqui: los modelos aun no existen al crear el sitio.
        from tiendas.panel import tiendas_del_panel
        from tiendas.services import ve_todas

        from .panel import resumen_panel, ventas_por_tienda

        from planes.services import estado_de_cuenta, resumen_para_el_administrador

        contexto = {}
        if request.user.has_perm('pedidos.view_pedido'):
            if ve_todas(request.user):
                # El administrador principal ve el total del sitio, el desglose por tienda y como van sus pagos.
                contexto = {
                    'resumen': resumen_panel(), 'ventas_por_tienda': ventas_por_tienda(),
                    'cobros': resumen_para_el_administrador(),
                }
            else:
                tiendas = tiendas_del_panel(request)
                contexto = {
                    'resumen': resumen_panel(tiendas),
                    'title': 'Resumen de ' + (', '.join(tienda.nombre for tienda in tiendas) or 'tu tienda'),
                    # Su plan y lo que debe al sitio; y si no tiene cuentas, sus clientes no pueden transferirle.
                    'estados_de_cuenta': [estado_de_cuenta(tienda) for tienda in tiendas],
                    'tiendas_sin_cuentas': [t for t in tiendas if not t.cuentas.filter(activa=True).exists()],
                }
        contexto.update(extra_context or {})
        return super().index(request, extra_context=contexto)
