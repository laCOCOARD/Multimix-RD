from django import forms

from clientes.forms import ConEstilo, limpiar_telefono

from .models import RUBROS, SolicitudTienda

MINIMO_DESCRIPCION = 20
MAXIMO_DESCRIPCION = 600


class SolicitudTiendaForm(ConEstilo, forms.ModelForm):
    """Formulario de /vender/solicitar/. El navegador revisa lo basico (obligatorios, largos, correo y telefono) con
    los atributos de cada campo, y Django lo vuelve a revisar todo."""

    acepta = forms.BooleanField(
        label='Acepto que usen estos datos para revisar mi solicitud y contactarme',
        error_messages={'required': 'Marca la casilla para que podamos revisar tu solicitud.'},
    )
    # El modelo guarda 10 digitos; aqui se escribe como se quiera (809-555-1234) y clean_telefono lo limpia.
    telefono = forms.CharField(
        label='Teléfono o WhatsApp', max_length=16, help_text='Un número dominicano: 809, 829 u 849.',
        widget=forms.TextInput(attrs={
            'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '809-555-1234',
            # Lo basico: 10 u 11 digitos con espacios, guiones o parentesis; Django revisa el prefijo. Todo escapado:
            # los navegadores leen `pattern` con la bandera `v`, que no admite ( ) + . - sueltos dentro de [].
            'pattern': r'[\d\s\(\)\+\.\-]{10,16}',
        }),
    )
    # Honeypot: las personas no lo ven; los bots suelen llenarlo.
    sitio_web = forms.CharField(required=False)

    class Meta:
        model = SolicitudTienda
        fields = ['nombre_responsable', 'nombre_comercial', 'correo', 'telefono', 'rubro', 'descripcion', 'redes']
        labels = {
            'nombre_responsable': 'Tu nombre completo',
            'nombre_comercial': 'Nombre de tu negocio',
            'correo': 'Correo electrónico',
            'rubro': '¿A qué se dedica tu negocio?',
            'descripcion': '¿Qué vendes?',
            'redes': 'Instagram, Facebook o sitio web (opcional)',
        }
        help_texts = {
            'nombre_comercial': 'Como quieres que se llame tu tienda.',
            'rubro': 'El que más se parezca. Si no está, elige "Otro" y cuéntalo abajo.',
            'descripcion': f'Cuéntanos en pocas líneas qué productos ofreces ({MINIMO_DESCRIPCION} a '
                           f'{MAXIMO_DESCRIPCION} caracteres).',
            'redes': 'Nos ayuda a conocer tu negocio.',
        }
        widgets = {
            'nombre_responsable': forms.TextInput(attrs={'autocomplete': 'name', 'minlength': 3}),
            'nombre_comercial': forms.TextInput(attrs={'autocomplete': 'organization', 'minlength': 2}),
            'correo': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'descripcion': forms.Textarea(attrs={
                'rows': 4, 'minlength': MINIMO_DESCRIPCION, 'maxlength': MAXIMO_DESCRIPCION,
            }),
            'redes': forms.TextInput(attrs={'placeholder': '@minegocio o https://...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rubro = self.fields['rubro']
        rubro.choices = [('', 'Elige el rubro'), *RUBROS]
        # Que lo elija: sin marcar "Otro" de entrada (el valor por defecto del modelo).
        if not self.instance.pk:
            self.initial.pop('rubro', None)
        rubro.widget.attrs['class'] = 'form-select'
        self.fields['acepta'].widget.attrs['class'] = 'form-check-input'
        self.fields['telefono'].widget.attrs['title'] = 'Escribe un teléfono dominicano: 809, 829 u 849.'

    def _texto(self, campo):
        return ' '.join(self.cleaned_data[campo].split())

    def clean_nombre_responsable(self):
        return self._texto('nombre_responsable')

    def clean_nombre_comercial(self):
        return self._texto('nombre_comercial')

    def clean_correo(self):
        return self.cleaned_data['correo'].strip().lower()

    def clean_telefono(self):
        return limpiar_telefono(self.cleaned_data['telefono'])

    def clean_descripcion(self):
        descripcion = self.cleaned_data['descripcion'].strip()
        if len(descripcion) < MINIMO_DESCRIPCION:
            raise forms.ValidationError(
                f'Cuéntanos un poco más: al menos {MINIMO_DESCRIPCION} caracteres sobre lo que vendes.'
            )
        if len(descripcion) > MAXIMO_DESCRIPCION:
            raise forms.ValidationError(f'Resúmelo en {MAXIMO_DESCRIPCION} caracteres o menos.')
        return descripcion

    def clean_redes(self):
        return self.cleaned_data['redes'].strip()

    def clean(self):
        datos = super().clean()
        if datos.get('sitio_web'):
            raise forms.ValidationError('No pudimos enviar tu solicitud. Inténtalo de nuevo.')
        return datos

    def datos_de_la_solicitud(self):
        return {campo: self.cleaned_data[campo] for campo in self.Meta.fields}
