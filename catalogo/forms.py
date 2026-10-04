from django import forms

ORDENES = [
    ('nuevos', 'Más nuevos'),
    ('precio_asc', 'Precio: menor a mayor'),
    ('precio_desc', 'Precio: mayor a menor'),
    ('vendidos', 'Más vendidos'),
]


class FiltroCatalogoForm(forms.Form):
    q = forms.CharField(required=False, max_length=80)
    precio_min = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2)
    precio_max = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2)
    oferta = forms.BooleanField(required=False)
    disponibles = forms.BooleanField(required=False)
    orden = forms.ChoiceField(required=False, choices=ORDENES)

    def filtros(self):
        """Filtros validos; los campos con errores se ignoran en lugar de romper el listado."""
        self.is_valid()
        return self.cleaned_data
