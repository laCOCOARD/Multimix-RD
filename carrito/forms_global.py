from django import forms

from core.telefonos import normalizar_telefono_rd
from core.validators import validar_imagen
from pedidos.models import Pedido


class CheckoutGlobalForm(forms.Form):
    """Formulario del checkout del carrito global. El metodo de pago es siempre transferencia al sitio."""

    nombre = forms.CharField(label='Nombre completo', min_length=3, max_length=120)
    telefono = forms.CharField(
        label='Teléfono / WhatsApp', max_length=20,
        error_messages={'required': 'Escribe tu teléfono: lo usamos para coordinar tus pedidos.'},
    )
    metodo_entrega = forms.ChoiceField(
        label='¿Cómo quieres recibirlo?', choices=Pedido.Entrega.choices, widget=forms.RadioSelect,
    )
    sector = forms.CharField(label='Sector', max_length=80, required=False)
    direccion = forms.CharField(label='Calle y número', max_length=255, required=False)
    referencia = forms.CharField(label='Referencia (opcional)', max_length=255, required=False)
    notas = forms.CharField(
        label='Notas (opcional)', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3}),
    )
    avisos_whatsapp = forms.BooleanField(label='Avisarme por WhatsApp cuando cambie mi pedido', required=False)
    acepta_terminos = forms.BooleanField(
        label='Acepto los términos del sitio',
        error_messages={'required': 'Para confirmar el pedido debes aceptar los términos del sitio.'},
    )
    sitio_web = forms.CharField(required=False)  # honeypot

    def clean_nombre(self):
        return ' '.join(self.cleaned_data['nombre'].split())

    def clean_telefono(self):
        try:
            return normalizar_telefono_rd(self.cleaned_data['telefono'])
        except ValueError as error:
            raise forms.ValidationError(str(error)) from error

    def clean(self):
        datos = super().clean()
        if datos.get('sitio_web'):
            raise forms.ValidationError('No pudimos procesar tu pedido. Inténtalo de nuevo.')
        if datos.get('metodo_entrega') == Pedido.Entrega.ENVIO:
            if not (datos.get('sector') or '').strip():
                self.add_error('sector', 'Escribe tu sector.')
            if not (datos.get('direccion') or '').strip():
                self.add_error('direccion', 'Escribe la calle y el número.')
        return datos


class AvisoTransferenciaGlobalForm(forms.Form):
    referencia_transferencia = forms.CharField(max_length=60, required=False)
    comprobante = forms.ImageField(
        validators=[validar_imagen],
        error_messages={'required': 'Adjunta la foto o captura del comprobante de la transferencia.'},
    )
