from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm

from core.red import ip_del_cliente
from core.telefonos import normalizar_telefono_rd

from . import services


class ConEstilo:
    """Da a los campos las clases de Bootstrap que usa la tienda."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', 'form-control')


def limpiar_telefono(valor, obligatorio=True):
    if not valor and not obligatorio:
        return ''
    try:
        return normalizar_telefono_rd(valor)
    except ValueError as error:
        raise forms.ValidationError(str(error)) from error


class RegistroForm(ConEstilo, forms.Form):
    nombre = forms.CharField(label='Nombre completo', min_length=3, max_length=120,
                             widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    correo = forms.EmailField(label='Correo', max_length=150, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    telefono = forms.CharField(label='Teléfono / WhatsApp', max_length=20,
                               widget=forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '809-555-1234'}))
    clave = forms.CharField(label='Contraseña', strip=False, help_text='Al menos 8 caracteres; que no sea solo números.',
                            widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    clave_repetida = forms.CharField(label='Repite la contraseña', strip=False,
                                     widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    # Honeypot: las personas no lo ven; los bots suelen llenarlo.
    sitio_web = forms.CharField(required=False)

    def clean_nombre(self):
        return ' '.join(self.cleaned_data['nombre'].split())

    def clean_correo(self):
        correo = self.cleaned_data['correo'].strip().lower()
        if services.correo_en_uso(correo):
            raise forms.ValidationError('Ya hay una cuenta con ese correo. Inicia sesión o recupera tu contraseña.')
        return correo

    def clean_telefono(self):
        return limpiar_telefono(self.cleaned_data['telefono'])

    def clean(self):
        datos = super().clean()
        if datos.get('sitio_web'):
            raise forms.ValidationError('No pudimos crear tu cuenta. Inténtalo de nuevo.')
        clave, repetida = datos.get('clave'), datos.get('clave_repetida')
        if clave and repetida and clave != repetida:
            self.add_error('clave_repetida', 'Las dos contraseñas no coinciden.')
        elif clave:
            provisional = get_user_model()(username=datos.get('correo', ''), email=datos.get('correo', ''),
                                           first_name=datos.get('nombre', ''))
            try:
                password_validation.validate_password(clave, provisional)
            except forms.ValidationError as error:
                self.add_error('clave', error)
        return datos

    def save(self):
        datos = self.cleaned_data
        return services.registrar_cliente(datos['nombre'], datos['correo'], datos['clave'], datos['telefono'])


class EntrarForm(ConEstilo, AuthenticationForm):
    """Inicio de sesion con limite de intentos por conexion y correo."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'El correo o la contraseña no son correctos.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Correo'
        self.fields['username'].widget.attrs.update({'autocomplete': 'email', 'inputmode': 'email'})
        self.fields['password'].label = 'Contraseña'

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

    def clean(self):
        partes = (ip_del_cliente(self.request) or 'sin-ip', self.cleaned_data.get('username', ''))
        if services.bloqueado('entrar', *partes):
            raise forms.ValidationError('Demasiados intentos. Espera 15 minutos o recupera tu contraseña.')
        try:
            datos = super().clean()
        except forms.ValidationError:
            services.anotar_intento('entrar', *partes)
            raise
        services.olvidar_intentos('entrar', *partes)
        return datos


class PerfilForm(ConEstilo, forms.Form):
    nombre = forms.CharField(label='Nombre completo', min_length=3, max_length=120)
    telefono = forms.CharField(label='Teléfono / WhatsApp', max_length=20, required=False)
    sector = forms.CharField(label='Sector', max_length=80, required=False)
    direccion = forms.CharField(label='Calle y número', max_length=255, required=False)
    referencia = forms.CharField(label='Referencia de la dirección', max_length=255, required=False)

    def clean_nombre(self):
        return ' '.join(self.cleaned_data['nombre'].split())

    def clean_telefono(self):
        return limpiar_telefono(self.cleaned_data['telefono'], obligatorio=False)

    def guardar(self, usuario):
        datos = self.cleaned_data
        usuario.first_name = datos['nombre'][:150]
        usuario.last_name = ''
        usuario.save(update_fields=['first_name', 'last_name'])
        perfil = services.perfil_de(usuario)
        perfil.telefono, perfil.sector = datos['telefono'], datos['sector']
        perfil.direccion, perfil.referencia = datos['direccion'], datos['referencia']
        perfil.save()


class CambiarClaveForm(ConEstilo, PasswordChangeForm):
    pass


class RecuperarClaveForm(ConEstilo, PasswordResetForm):
    pass


class NuevaClaveForm(ConEstilo, SetPasswordForm):
    pass
