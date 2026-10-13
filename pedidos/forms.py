from django import forms

from core.telefonos import normalizar_telefono_rd
from core.validators import validar_imagen
from promociones.services import CuponInvalido

from .models import Pedido
from .services import metodos_pago_disponibles, zonas_activas


class CheckoutForm(forms.Form):
    nombre = forms.CharField(label='Nombre completo', min_length=3, max_length=120)
    telefono = forms.CharField(label='Teléfono / WhatsApp', max_length=20)
    correo = forms.EmailField(label='Correo (opcional)', required=False)
    metodo_entrega = forms.ChoiceField(
        label='¿Cómo quieres recibirlo?', choices=Pedido.Entrega.choices, widget=forms.RadioSelect,
    )
    zona = forms.ModelChoiceField(label='Zona de envío', queryset=None, required=False, empty_label='Elige tu zona')
    sector = forms.CharField(label='Sector', max_length=80, required=False)
    direccion = forms.CharField(label='Calle y número', max_length=255, required=False)
    referencia = forms.CharField(label='Referencia (opcional)', max_length=255, required=False)
    metodo_pago = forms.ChoiceField(label='Forma de pago', choices=Pedido.Pago.choices, widget=forms.RadioSelect)
    transferencia_realizada = forms.BooleanField(label='Ya hice la transferencia', required=False)
    referencia_transferencia = forms.CharField(
        label='Referencia de la transferencia (opcional)', max_length=60, required=False,
    )
    cupon = forms.CharField(label='Cupón', max_length=30, required=False)
    notas = forms.CharField(
        label='Notas (opcional)', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3}),
    )
    acepta_terminos = forms.BooleanField(
        label='Acepto los términos del sitio',
        error_messages={'required': 'Para confirmar el pedido debes aceptar los términos del sitio.'},
    )
    # Honeypot: las personas no lo ven; los bots suelen llenarlo.
    sitio_web = forms.CharField(required=False)

    def __init__(self, *args, carrito, **kwargs):
        super().__init__(*args, **kwargs)
        self.carrito = carrito
        self.fields['zona'].queryset = zonas_activas(carrito.tienda)

    def clean_nombre(self):
        return ' '.join(self.cleaned_data['nombre'].split())

    def clean_telefono(self):
        try:
            return normalizar_telefono_rd(self.cleaned_data['telefono'])
        except ValueError as error:
            raise forms.ValidationError(str(error)) from error

    def clean_cupon(self):
        """El cupon se valida contra el carrito y queda guardado en la sesion."""
        codigo = self.cleaned_data['cupon'].strip()
        if not codigo:
            self.carrito.quitar_cupon()
            return ''
        try:
            return self.carrito.aplicar_cupon(codigo).codigo
        except CuponInvalido as error:
            self.carrito.quitar_cupon()
            raise forms.ValidationError(error.mensaje) from error

    def clean(self):
        datos = super().clean()
        if datos.get('sitio_web'):
            raise forms.ValidationError('No pudimos procesar tu pedido. Inténtalo de nuevo.')

        entrega = datos.get('metodo_entrega')
        if entrega == Pedido.Entrega.ENVIO:
            if not datos.get('zona'):
                self.add_error('zona', 'Elige tu zona de envío.')
            if not (datos.get('sector') or '').strip():
                self.add_error('sector', 'Escribe tu sector.')
            if not (datos.get('direccion') or '').strip():
                self.add_error('direccion', 'Escribe la calle y el número.')

        pago = datos.get('metodo_pago')
        if entrega and pago and pago not in metodos_pago_disponibles(entrega, self.carrito.tienda):
            self.add_error('metodo_pago', 'Esa forma de pago no está disponible para la entrega elegida.')
        return datos


class AvisoTransferenciaForm(forms.Form):
    referencia_transferencia = forms.CharField(max_length=60, required=False)
    # forms.ImageField comprueba con Pillow que el archivo sea de verdad una imagen.
    comprobante = forms.ImageField(required=False, validators=[validar_imagen])
