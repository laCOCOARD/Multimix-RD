from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.utils.html import format_html_join

from tiendas.panel import AdminDeTienda

from . import services
from .models import Pregunta, Resena


@admin.register(Resena)
class ResenaAdmin(AdminDeTienda, admin.ModelAdmin):
    """Moderacion de reseñas. Cada tienda ve las suyas; publicarlas o rechazarlas es del administrador principal,
    para que una tienda no pueda esconder las opiniones que no le gustan."""

    list_display = ['producto', 'autor', 'estrellas', 'comentario_corto', 'con_fotos', 'compra_verificada', 'estado', 'creado']
    list_filter = ['estado', 'estrellas', 'compra_verificada']
    search_fields = ['producto__nombre', 'comentario', 'usuario__email']
    list_select_related = ['producto', 'usuario']
    actions = ['publicar', 'rechazar']
    fields = ['producto', 'tienda', 'autor', 'estrellas', 'comentario', 'fotos', 'compra_verificada', 'estado', 'creado']
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('fotos')

    def has_add_permission(self, request):
        return False

    def _moderar(self, request, queryset, estado, hecho):
        if not request.user.has_perm('opiniones.change_resena'):
            raise PermissionDenied
        self.message_user(request, f'{queryset.update(estado=estado)} reseña(s) {hecho}.')

    @admin.action(description='Publicar', permissions=['change'])
    def publicar(self, request, queryset):
        self._moderar(request, queryset, Resena.Estado.APROBADA, 'publicadas')

    @admin.action(description='Rechazar (no se muestra)', permissions=['change'])
    def rechazar(self, request, queryset):
        self._moderar(request, queryset, Resena.Estado.RECHAZADA, 'rechazadas')

    @admin.display(description='Cliente')
    def autor(self, resena):
        return resena.usuario.get_full_name() or resena.usuario.email

    @admin.display(description='Comentario')
    def comentario_corto(self, resena):
        return resena.comentario[:90]

    @admin.display(description='Fotos')
    def con_fotos(self, resena):
        total = len(resena.fotos.all())
        return total or '—'

    @admin.display(description='Fotos del cliente')
    def fotos(self, resena):
        fotos = resena.fotos.all()
        if not fotos:
            return 'Sin fotos'
        return format_html_join(
            ' ', '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" alt="" class="panel-foto-previa"></a>',
            ((foto.imagen.url,) for foto in fotos),
        )


@admin.register(Pregunta)
class PreguntaAdmin(AdminDeTienda, admin.ModelAdmin):
    """Preguntas de los clientes. La tienda escribe la respuesta; al guardarla se publica y se avisa al cliente."""

    list_display = ['texto_corto', 'producto', 'autor', 'estado', 'creado']
    list_filter = ['estado', 'creado']
    search_fields = ['texto', 'respuesta', 'producto__nombre', 'producto__sku']
    list_select_related = ['producto', 'usuario']
    actions = ['ocultar', 'publicar']
    fields = ['producto', 'tienda', 'autor', 'creado', 'texto', 'respuesta', 'estado', 'respondida_en', 'respondida_por']
    readonly_fields = ['producto', 'tienda', 'autor', 'creado', 'texto', 'estado', 'respondida_en', 'respondida_por']

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        # Responder pasa por la capa de servicios: publica la pregunta y le avisa al cliente.
        if obj.respuesta.strip():
            services.responder(obj, obj.respuesta, request.user)
        else:
            obj.save()

    @admin.action(description='Ocultar (no se muestra en la ficha)', permissions=['change'])
    def ocultar(self, request, queryset):
        self.message_user(request, f'{services.ocultar_preguntas(queryset)} pregunta(s) ocultas.')

    @admin.action(description='Publicar las ya respondidas', permissions=['change'])
    def publicar(self, request, queryset):
        total = queryset.exclude(respuesta='').update(estado=Pregunta.Estado.PUBLICADA)
        sin_respuesta = queryset.filter(respuesta='').count()
        self.message_user(request, f'{total} pregunta(s) publicadas.')
        if sin_respuesta:
            self.message_user(request, f'{sin_respuesta} sin respuesta: respóndelas primero.', messages.WARNING)

    @admin.display(description='Pregunta')
    def texto_corto(self, pregunta):
        return pregunta.texto[:90]

    @admin.display(description='Cliente')
    def autor(self, pregunta):
        return pregunta.usuario.get_full_name() or pregunta.usuario.email
