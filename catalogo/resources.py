"""Importacion y exportacion de productos en Excel (django-import-export)."""
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import Categoria, Producto

COLUMNAS = [
    'sku', 'nombre', 'categoria', 'descripcion', 'precio', 'precio_oferta',
    'oferta_inicio', 'oferta_fin', 'stock_almacen', 'destacado', 'nuevo', 'activo',
]
FILA_DE_EJEMPLO = [
    'HOG-001', 'Lámpara de mesa LED', 'Hogar', 'Luz cálida regulable.', '1250.00', '990.00',
    '2026-01-15 08:00:00', '2026-01-31 23:59:00', 25, 1, 0, 1,
]


class CategoriaPorNombreWidget(ForeignKeyWidget):
    """Busca la categoria por nombre y la crea si todavia no existe."""

    def clean(self, value, row=None, **kwargs):
        nombre = (value or '').strip()
        if not nombre:
            raise ValueError('La categoría es obligatoria.')
        categoria = Categoria.objects.filter(nombre__iexact=nombre).first()
        return categoria or Categoria.objects.create(nombre=nombre)


class ProductoResource(resources.ModelResource):
    categoria = fields.Field(
        column_name='categoria', attribute='categoria', widget=CategoriaPorNombreWidget(Categoria, 'nombre'),
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

    def before_import_row(self, row, **kwargs):
        if row.get('sku') is not None:
            row['sku'] = str(row['sku']).strip().upper()
