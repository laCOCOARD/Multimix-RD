"""Importacion y exportacion de productos en Excel (django-import-export)."""
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import Categoria, Producto

COLUMNAS = [
    'sku', 'nombre', 'categoria', 'descripcion', 'precio', 'precio_oferta',
    'oferta_inicio', 'oferta_fin', 'disponibilidad', 'controla_stock', 'stock_almacen', 'destacado', 'nuevo',
    'activo', 'marca', 'variante_de', 'nombre_variante', 'tipo_variante',
]
FILA_DE_EJEMPLO = [
    'HOG-001', 'Lámpara de mesa LED', 'Hogar', 'Luz cálida regulable.', '1250.00', '990.00',
    '2026-01-15 08:00:00', '2026-01-31 23:59:00', 'disponible', 0, 0, 1, 0, 1, 'Lumina', '', 'Blanca', 'Color',
]


class CategoriaPorNombreWidget(ForeignKeyWidget):
    """Busca la categoria por nombre. Con `crear` la agrega si no existe (solo el administrador principal)."""

    crear = True

    def clean(self, value, row=None, **kwargs):
        nombre = (value or '').strip()
        if not nombre:
            raise ValueError('La categoría es obligatoria.')
        categoria = Categoria.objects.filter(nombre__iexact=nombre).first()
        if categoria is None and not self.crear:
            raise ValueError(f'La categoría "{nombre}" no existe. Pide al administrador del sitio que la cree.')
        return categoria or Categoria.objects.create(nombre=nombre)


class PrincipalPorSkuWidget(ForeignKeyWidget):
    """La columna `variante_de` trae el SKU del producto principal, que se busca solo en la tienda que se importa."""

    tienda = None

    def clean(self, value, row=None, **kwargs):
        sku = str(value or '').strip().upper()
        if not sku:
            return None
        principal = Producto.objects.filter(tienda=self.tienda, sku=sku).first() if self.tienda else None
        if principal is None:
            raise ValueError(f'No hay un producto con el SKU {sku} en esta tienda (columna variante_de).')
        return principal

    def render(self, value, obj=None, **kwargs):
        return value.sku if value else ''


class ProductoResource(resources.ModelResource):
    """Importa en una sola tienda: el `sku` identifica el producto dentro de ella.

    El panel pasa la `tienda` elegida en el formulario; lo de otras tiendas no se lee ni se toca.
    """

    categoria = fields.Field(
        column_name='categoria', attribute='categoria', widget=CategoriaPorNombreWidget(Categoria, 'nombre'),
    )
    variante_de = fields.Field(
        column_name='variante_de', attribute='variante_de', widget=PrincipalPorSkuWidget(Producto, 'sku'),
    )

    class Meta:
        model = Producto
        fields = COLUMNAS
        export_order = COLUMNAS
        import_id_fields = ['sku']
        skip_unchanged = True
        report_skipped = True
        # Valida cada fila con las mismas reglas del modelo (oferta < precio, stock, etc.).
        clean_model_instances = True

    def __init__(self, tienda=None, crear_categorias=True, **kwargs):
        super().__init__(**kwargs)
        self.tienda = tienda
        self.fields['categoria'].widget.crear = crear_categorias
        self.fields['variante_de'].widget.tienda = tienda

    def get_queryset(self):
        consulta = super().get_queryset()
        return consulta if self.tienda is None else consulta.filter(tienda=self.tienda)

    def before_import(self, dataset, **kwargs):
        if self.tienda is None:
            raise ValueError('Elige la tienda en la que se importan los productos.')
        super().before_import(dataset, **kwargs)

    def init_instance(self, row=None):
        producto = super().init_instance(row)
        producto.tienda = self.tienda
        return producto

    def before_import_row(self, row, **kwargs):
        if row.get('sku') is not None:
            row['sku'] = str(row['sku']).strip().upper()
