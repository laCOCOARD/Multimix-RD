from decimal import ROUND_HALF_UP, Decimal

import tablib
from django import forms
from django.contrib import admin, messages
from django.db.models import Count, F
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

from core.models import ConfiguracionTienda
from core.templatetags.moneda import formatear_monto

from .models import Categoria, FotoProducto, Producto, q_oferta_vigente
from .resources import COLUMNAS, FILA_DE_EJEMPLO, ProductoResource


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'cantidad_productos', 'activa', 'orden']
    list_editable = ['activa', 'orden']
    list_filter = ['activa']
    search_fields = ['nombre']
    prepopulated_fields = {'slug': ['nombre']}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total_productos=Count('productos'))

    @admin.display(description='Productos', ordering='total_productos')
    def cantidad_productos(self, categoria):
        return categoria.total_productos


class FotoProductoInline(admin.TabularInline):
    model = FotoProducto
    extra = 1
    fields = ['vista_previa', 'imagen', 'orden', 'principal']
    readonly_fields = ['vista_previa']

    @admin.display(description='Vista previa')
    def vista_previa(self, foto):
        if foto.pk and foto.imagen:
            return format_html('<img src="{}" alt="" class="panel-foto-previa" loading="lazy">', foto.imagen.url)
        return '—'


class EnOfertaFilter(admin.SimpleListFilter):
    title = 'oferta'
    parameter_name = 'oferta'

    def lookups(self, request, model_admin):
        return [('vigente', 'En oferta ahora'), ('con_precio', 'Con precio de oferta'), ('sin', 'Sin oferta')]

    def queryset(self, request, queryset):
        if self.value() == 'vigente':
            return queryset.filter(q_oferta_vigente())
        if self.value() == 'con_precio':
            return queryset.filter(precio_oferta__isnull=False)
        if self.value() == 'sin':
            return queryset.filter(precio_oferta__isnull=True)
        return queryset


class StockFilter(admin.SimpleListFilter):
    title = 'nivel de stock'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return [('bajo', 'Stock bajo'), ('agotado', 'Agotado'), ('normal', 'Stock normal')]

    def queryset(self, request, queryset):
        umbral = ConfiguracionTienda.obtener().umbral_stock_bajo
        queryset = queryset.annotate(_disponible=F('stock_almacen') - F('stock_reservado'))
        if self.value() == 'bajo':
            return queryset.filter(_disponible__gt=0, _disponible__lte=umbral)
        if self.value() == 'agotado':
            return queryset.filter(_disponible__lte=0)
        if self.value() == 'normal':
            return queryset.filter(_disponible__gt=umbral)
        return queryset


class OfertaMasivaForm(forms.Form):
    porcentaje = forms.IntegerField(
        label='Descuento (%)', min_value=1, max_value=95,
        help_text='Se calcula sobre el precio normal de cada producto.',
    )
    inicio = forms.DateTimeField(
        label='Inicio de la oferta', required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        help_text='Vacío = empieza de inmediato.',
    )
    fin = forms.DateTimeField(
        label='Fin de la oferta', required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        help_text='Vacío = sin fecha de fin.',
    )

    def clean(self):
        datos = super().clean()
        if datos.get('inicio') and datos.get('fin') and datos['fin'] <= datos['inicio']:
            self.add_error('fin', 'La oferta debe terminar después de su inicio.')
        return datos


@admin.register(Producto)
class ProductoAdmin(ImportExportModelAdmin):
    resource_classes = [ProductoResource]
    import_export_change_list_template = 'admin/catalogo/producto/change_list.html'

    list_display = [
        'miniatura', 'nombre', 'sku', 'categoria', 'precio_formateado', 'oferta', 'stock_almacen',
        'stock_reservado', 'disponible', 'destacado', 'nuevo', 'activo',
    ]
    list_display_links = ['miniatura', 'nombre']
    list_editable = ['destacado', 'nuevo', 'activo']
    list_filter = ['categoria', 'activo', EnOfertaFilter, StockFilter, 'destacado', 'nuevo']
    search_fields = ['nombre', 'sku', 'texto_busqueda']
    list_per_page = 40
    prepopulated_fields = {'slug': ['nombre']}
    readonly_fields = ['stock_reservado', 'stock_disponible_actual', 'creado', 'actualizado']
    inlines = [FotoProductoInline]
    actions = ['destacar', 'quitar_destacado', 'activar', 'desactivar', 'poner_oferta', 'quitar_oferta']
    fieldsets = [
        (None, {'fields': ['nombre', 'slug', 'sku', 'categoria', 'descripcion']}),
        ('Precio', {'fields': ['precio', 'precio_oferta', 'oferta_inicio', 'oferta_fin']}),
        ('Inventario', {'fields': ['stock_almacen', 'stock_reservado', 'stock_disponible_actual']}),
        ('Visibilidad', {'fields': ['activo', 'destacado', 'nuevo', 'creado', 'actualizado']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('categoria').prefetch_related('fotos')

    def get_urls(self):
        propias = [
            path(
                'plantilla-excel/', self.admin_site.admin_view(self.descargar_plantilla),
                name='catalogo_producto_plantilla',
            ),
        ]
        return propias + super().get_urls()

    def descargar_plantilla(self, request):
        """Excel con las columnas esperadas y una fila de ejemplo."""
        plantilla = tablib.Dataset(FILA_DE_EJEMPLO, headers=COLUMNAS, title='Productos')
        respuesta = HttpResponse(
            plantilla.export('xlsx'),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        respuesta['Content-Disposition'] = 'attachment; filename="plantilla_productos.xlsx"'
        return respuesta

    # --- Columnas -------------------------------------------------------------------

    @admin.display(description='Foto')
    def miniatura(self, producto):
        foto = producto.foto_principal
        if foto:
            return format_html('<img src="{}" alt="" class="panel-miniatura" loading="lazy">', foto.imagen.url)
        return format_html('<span class="panel-miniatura panel-sin-foto">{}</span>', '—')

    @admin.display(description='Precio', ordering='precio')
    def precio_formateado(self, producto):
        return formatear_monto(producto.precio)

    @admin.display(description='Oferta', ordering='precio_oferta')
    def oferta(self, producto):
        if producto.precio_oferta is None:
            return '—'
        if producto.en_oferta:
            return format_html(
                '<span class="panel-etiqueta panel-ok">{} (-{}%)</span>',
                formatear_monto(producto.precio_oferta), producto.porcentaje_descuento,
            )
        return format_html(
            '<span class="panel-etiqueta panel-inactiva" title="Fuera de vigencia">{}</span>',
            formatear_monto(producto.precio_oferta),
        )

    @admin.display(description='Disponible')
    def disponible(self, producto):
        if producto.agotado:
            clase, texto = 'panel-agotado', 'Agotado'
        elif producto.stock_bajo:
            clase, texto = 'panel-bajo', producto.stock_disponible
        else:
            clase, texto = 'panel-ok', producto.stock_disponible
        return format_html('<span class="panel-etiqueta {}">{}</span>', clase, texto)

    @admin.display(description='Disponible para la venta')
    def stock_disponible_actual(self, producto):
        return producto.stock_disponible if producto.pk else '—'

    # --- Acciones masivas -----------------------------------------------------------

    @admin.action(description='Marcar como destacados')
    def destacar(self, request, queryset):
        self.message_user(request, f'{queryset.update(destacado=True)} productos destacados.')

    @admin.action(description='Quitar de destacados')
    def quitar_destacado(self, request, queryset):
        self.message_user(request, f'{queryset.update(destacado=False)} productos ya no están destacados.')

    @admin.action(description='Activar')
    def activar(self, request, queryset):
        self.message_user(request, f'{queryset.update(activo=True)} productos activados.')

    @admin.action(description='Desactivar')
    def desactivar(self, request, queryset):
        self.message_user(request, f'{queryset.update(activo=False)} productos desactivados.')

    @admin.action(description='Quitar oferta')
    def quitar_oferta(self, request, queryset):
        total = queryset.update(precio_oferta=None, oferta_inicio=None, oferta_fin=None)
        self.message_user(request, f'Se quitó la oferta de {total} productos.')

    # El %% es necesario: el admin aplica formato con % a la descripcion de cada accion.
    @admin.action(description='Poner oferta de X %% con fechas')
    def poner_oferta(self, request, queryset):
        formulario = OfertaMasivaForm(request.POST if 'aplicar' in request.POST else None)
        if formulario.is_valid():
            factor = Decimal(100 - formulario.cleaned_data['porcentaje']) / Decimal(100)
            productos = []
            for producto in queryset:
                oferta = (producto.precio * factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                # Con precios de centavos el redondeo puede igualar el precio; esos se omiten.
                if not 0 < oferta < producto.precio:
                    continue
                producto.precio_oferta = oferta
                producto.oferta_inicio = formulario.cleaned_data['inicio']
                producto.oferta_fin = formulario.cleaned_data['fin']
                productos.append(producto)
            Producto.objects.bulk_update(productos, ['precio_oferta', 'oferta_inicio', 'oferta_fin'])
            self.message_user(
                request,
                f'Oferta de {formulario.cleaned_data["porcentaje"]} % aplicada a {len(productos)} productos.',
                messages.SUCCESS,
            )
            return None
        return render(request, 'admin/catalogo/producto/oferta_masiva.html', {
            **self.admin_site.each_context(request),
            'title': 'Poner oferta a los productos seleccionados',
            'formulario': formulario,
            'productos': queryset,
            'opts': self.model._meta,
            'media': self.media,
        })
