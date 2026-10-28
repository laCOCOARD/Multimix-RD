"""Gustos del cliente (pedido del dueño el 2026-10-27): cuatro preguntas de seleccion que se hacen una sola vez, al
crear la cuenta, para ordenar mejor lo que se le muestra.

Se usan asi (y en ningun otro lado):
- categorias: van primero en la portada, en el buscador (si no eligio otro orden) y suman en las promociones;
- busca: ofertas o lo nuevo suman en las promociones;
- presupuesto: lo que esta en su rango suma en las promociones;
- entrega: el checkout llega con esa forma de entrega marcada (si la tienda hace envios).
Se guardan en su perfil, no se comparten con las tiendas y se cambian o borran en "Mi cuenta".
"""
from decimal import Decimal

from django import forms

BUSCA = [
    ('ofertas', 'Ofertas y buenos precios'),
    ('nuevos', 'Lo más nuevo'),
    ('marcas', 'Marcas reconocidas'),
    ('locales', 'Productos de emprendedores locales'),
]
PRESUPUESTO = [
    ('hasta_1000', 'Hasta RD$ 1,000'),
    ('1000_3000', 'De RD$ 1,000 a 3,000'),
    ('3000_6000', 'De RD$ 3,000 a 6,000'),
    ('mas_6000', 'Más de RD$ 6,000'),
]
RANGOS = {
    'hasta_1000': (Decimal('0'), Decimal('1000')),
    '1000_3000': (Decimal('1000'), Decimal('3000')),
    '3000_6000': (Decimal('3000'), Decimal('6000')),
    'mas_6000': (Decimal('6000'), None),
}
ENTREGA = [
    ('envio', 'A domicilio'),
    ('recoger', 'Recoger en la tienda'),
    ('igual', 'Me da igual'),
]


class GustosForm(forms.Form):
    categorias = forms.MultipleChoiceField(
        label='¿Qué te gusta comprar?', required=False, widget=forms.CheckboxSelectMultiple,
        help_text='Elige las que quieras.',
    )
    busca = forms.ChoiceField(label='¿Qué buscas más seguido?', required=False, choices=BUSCA, widget=forms.RadioSelect)
    presupuesto = forms.ChoiceField(
        label='¿Cuánto sueles gastar en una compra?', required=False, choices=PRESUPUESTO, widget=forms.RadioSelect,
    )
    entrega = forms.ChoiceField(
        label='¿Cómo prefieres recibir tus compras?', required=False, choices=ENTREGA, widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        from catalogo.models import Categoria

        super().__init__(*args, **kwargs)
        # Las categorias principales del sitio que tienen algo a la venta: lo que de verdad se puede mostrar.
        from catalogo.services import categorias_del_sitio

        self.fields['categorias'].choices = [(str(c.pk), c.nombre) for c in categorias_del_sitio()] or [
            (str(c.pk), c.nombre) for c in Categoria.objects.filter(activa=True, padre__isnull=True).order_by('nombre')
        ]

    def gustos(self):
        datos = self.cleaned_data
        gustos = {'categorias': [int(pk) for pk in datos['categorias']]}
        for campo in ('busca', 'presupuesto', 'entrega'):
            if datos.get(campo):
                gustos[campo] = datos[campo]
        return {clave: valor for clave, valor in gustos.items() if valor}


def de(usuario):
    """Los gustos de un cliente con sesion; {} si no tiene o no contesto."""
    if not getattr(usuario, 'is_authenticated', False) or usuario.is_staff:
        return {}
    perfil = getattr(usuario, 'perfil', None)
    return dict(perfil.gustos or {}) if perfil else {}


def en_su_presupuesto(gustos, precio):
    rango = RANGOS.get(gustos.get('presupuesto'))
    if not rango or precio is None:
        return False
    minimo, maximo = rango
    return precio >= minimo and (maximo is None or precio <= maximo)
