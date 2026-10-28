from django.contrib import admin

from clientes.forms import EntrarAlPanelForm


# Menu del vendedor: agrupado por lo que hace en el dia, con nombres simples. (grupo, [(app, modelo, nombre)]).
# Lo que no esta aqui y el vendedor puede ver va al final en "Más".
MENU_DEL_VENDEDOR = [
    ('Pedidos', [
        ('pedidos', 'pedido', 'Pedidos'),
        ('pedidos', 'solicituddevolucion', 'Devoluciones'),
        ('pagos', 'pago', 'Pagos de clientes'),
    ]),
    ('Productos', [
        ('catalogo', 'producto', 'Mis productos'),
        ('catalogo', 'avisodisponible', 'Clientes esperando un producto'),
    ]),
    ('Clientes', [
        ('opiniones', 'pregunta', 'Preguntas'),
        ('opiniones', 'resena', 'Reseñas'),
    ]),
    ('Mi tienda', [
        ('tiendas', 'tienda', 'Datos de la tienda'),
        ('tiendas', 'cuentabancaria', 'Cuentas de banco'),
        ('pedidos', 'zonaenvio', 'Zonas de envío'),
        ('tiendas', 'banner', 'Banners de la tienda'),
    ]),
    ('Promociones', [
        ('promociones', 'cupon', 'Cupones'),
        ('planes', 'anuncio', 'Anuncios en la portada'),
        ('planes', 'video', 'Videos'),
    ]),
    ('Mi plan', [
        ('planes', 'cargo', 'Mensualidades y pagos'),
        ('planes', 'plan', 'Planes'),
        ('pagos', 'liquidacion', 'Liquidaciones'),
    ]),
]


def agrupar_para_el_vendedor(app_list):
    """Reordena el menu de Django en los grupos de MENU_DEL_VENDEDOR. Solo cambia nombres y orden, no permisos."""
    modelos = {(app['app_label'], m['object_name'].lower()): m for app in app_list for m in app['models']}
    grupos = []
    for numero, (nombre, entradas) in enumerate(MENU_DEL_VENDEDOR):
        lista = []
        for app_label, modelo, etiqueta in entradas:
            encontrado = modelos.pop((app_label, modelo), None)
            if encontrado:
                lista.append({**encontrado, 'name': etiqueta})
        if lista:
            grupos.append({'name': nombre, 'app_label': f'grupo{numero}', 'app_url': lista[0]['admin_url'],
                           'has_module_perms': True, 'models': lista})
    if modelos:
        resto = sorted(modelos.values(), key=lambda m: m['name'])
        grupos.append({'name': 'Más', 'app_label': 'grupo-mas', 'app_url': resto[0]['admin_url'],
                       'has_module_perms': True, 'models': resto})
    return grupos


class PanelAdminSite(admin.AdminSite):
    site_header = 'Multimix RD'
    site_title = 'Panel Multimix RD'
    index_title = 'Resumen del sitio'
    site_url = '/'
    # Con limite de intentos: la pantalla de Django no lo trae.
    login_form = EntrarAlPanelForm

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label is None and not request.user.is_superuser:
            return agrupar_para_el_vendedor(app_list)
        return app_list

    def index(self, request, extra_context=None):
        # Se importa aqui: los modelos aun no existen al crear el sitio.
        from tiendas.panel import tiendas_del_panel
        from tiendas.services import solicitudes_pendientes, ve_todas

        from . import metricas
        from .panel import primeros_pasos, resumen_panel, tareas_de_la_tienda, ventas_por_tienda

        from planes.services import estado_de_cuenta, resumen_para_el_administrador

        contexto = {}
        if request.user.has_perm('pedidos.view_pedido'):
            if ve_todas(request.user):
                # El administrador principal ve el total del sitio, el desglose por tienda y como van sus pagos.
                contexto = {
                    'resumen': resumen_panel(), 'ventas_por_tienda': ventas_por_tienda(),
                    'cobros': resumen_para_el_administrador(),
                    # Negocios que pidieron abrir su tienda desde /vender/solicitar/.
                    'solicitudes_pendientes': solicitudes_pendientes(),
                    # Indicadores del sitio y actividad de todas las tiendas (core.metricas).
                    'indicadores': metricas.indicadores_del_sitio(),
                    'actividad': metricas.resumen(),
                }
            else:
                tiendas = tiendas_del_panel(request)
                contexto = {
                    'resumen': resumen_panel(tiendas),
                    'title': 'Inicio',
                    # Su plan y lo que debe al sitio; y si no tiene cuentas, sus clientes no pueden transferirle.
                    'estados_de_cuenta': [estado_de_cuenta(tienda) for tienda in tiendas],
                    'tiendas_sin_cuentas': [t for t in tiendas if not t.cuentas.filter(activa=True).exists()],
                    # Solo la actividad de sus tiendas.
                    'actividad': metricas.resumen(tiendas),
                    # Inicio del dueño de tienda: que hacer ahora y lo que le falta para empezar a vender.
                    'es_vendedor': True,
                    'tiendas': tiendas,
                    'tareas': tareas_de_la_tienda(tiendas),
                    'primeros_pasos': [
                        (tienda, pasos) for tienda, pasos in ((t, primeros_pasos(t)) for t in tiendas)
                        if not all(paso['hecho'] for paso in pasos)
                    ],
                }
        contexto.update(extra_context or {})
        return super().index(request, extra_context=contexto)
