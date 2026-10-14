from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as acceso
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from catalogo.models import Producto

from core.red import ip_del_cliente
from pedidos.models import Pedido

from . import services
from .forms import CambiarClaveForm, EntrarForm, NuevaClaveForm, PerfilForm, RecuperarClaveForm, RegistroForm

PLANTILLA = 'clientes/formulario.html'
PEDIDOS_POR_PAGINA = 10


def _destino(request, por_defecto='clientes:cuenta'):
    """A donde volver despues de entrar o registrarse: solo a una pagina de este mismo sitio."""
    siguiente = request.POST.get('next') or request.GET.get('next') or ''
    if url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return siguiente
    return por_defecto


@sensitive_post_parameters('clave', 'clave_repetida')
@never_cache
def registro(request):
    if request.user.is_authenticated:
        return redirect('clientes:cuenta')
    ip = ip_del_cliente(request) or 'sin-ip'
    formulario = RegistroForm(request.POST or None)
    if request.method == 'POST':
        if services.bloqueado('registro', ip):
            formulario.add_error(None, 'Se crearon varias cuentas desde tu conexión. Espera unos minutos.')
        elif formulario.is_valid():
            services.anotar_intento('registro', ip)
            usuario = formulario.save()
            login(request, usuario, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'¡Bienvenido, {usuario.first_name}! Tu cuenta ya está creada.')
            return redirect(_destino(request))
    return render(request, PLANTILLA, {
        'formulario': formulario,
        'titulo': 'Crear cuenta',
        'intro': 'Con tu cuenta ves tus pedidos y no tienes que escribir tus datos en cada compra.',
        'boton': 'Crear mi cuenta',
        'siguiente': _destino(request, ''),
        'enlaces': [('clientes:entrar', '¿Ya tienes cuenta? Inicia sesión')],
    })


class Entrar(acceso.LoginView):
    template_name = PLANTILLA
    authentication_form = EntrarForm
    redirect_authenticated_user = True
    next_page = reverse_lazy('clientes:cuenta')
    extra_context = {
        'titulo': 'Iniciar sesión',
        'boton': 'Entrar',
        'enlaces': [
            ('clientes:registro', '¿No tienes cuenta? Créala gratis'),
            ('clientes:recuperar', 'Olvidé mi contraseña'),
        ],
    }

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(formulario=contexto['form'], siguiente=_destino(self.request, ''))
        return contexto


class Salir(acceso.LogoutView):
    next_page = reverse_lazy('tiendas:portada')


@login_required
def cuenta(request):
    """Los pedidos del cliente en todas las tiendas. Solo los suyos."""
    pedidos = Pedido.objects.filter(cliente=request.user).select_related('tienda').order_by('-creado', '-id')
    return render(request, 'clientes/cuenta.html', {
        'pagina': Paginator(pedidos, PEDIDOS_POR_PAGINA).get_page(request.GET.get('pagina')),
        'perfil': services.perfil_de(request.user),
    })


@login_required
def perfil(request):
    usuario = request.user
    datos = services.datos_para_el_checkout(usuario)
    formulario = PerfilForm(request.POST or None, initial=datos)
    if request.method == 'POST' and formulario.is_valid():
        formulario.guardar(usuario)
        messages.success(request, 'Guardamos tus datos.')
        return redirect('clientes:cuenta')
    return render(request, PLANTILLA, {
        'formulario': formulario,
        'titulo': 'Mis datos',
        'intro': f'Tu correo es {usuario.email}. Esta dirección se usa para llenar tus próximos pedidos.',
        'boton': 'Guardar',
        'enlaces': [('clientes:cuenta', 'Volver a mi cuenta')],
    })


@login_required
def favoritos(request):
    return render(request, 'clientes/favoritos.html', {'productos': services.productos_favoritos(request.user)})


@require_POST
@login_required
def alternar_favorito(request, producto_id):
    producto = get_object_or_404(Producto.objects.activos(), pk=producto_id)
    if services.alternar_favorito(request.user, producto):
        messages.success(request, f'Guardamos "{producto.nombre}" en tus favoritos.')
    else:
        messages.info(request, f'Quitamos "{producto.nombre}" de tus favoritos.')
    return redirect(_destino(request, producto.get_absolute_url()))


class _ConFormulario:
    """Las vistas de Django llaman `form` al formulario; la plantilla de la tienda lo llama `formulario`."""

    template_name = PLANTILLA

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['formulario'] = contexto.get('form')
        return contexto


class CambiarClave(_ConFormulario, acceso.PasswordChangeView):
    form_class = CambiarClaveForm
    success_url = reverse_lazy('clientes:cuenta')
    extra_context = {
        'titulo': 'Cambiar contraseña', 'boton': 'Cambiar contraseña',
        'enlaces': [('clientes:cuenta', 'Volver a mi cuenta')],
    }

    def form_valid(self, form):
        messages.success(self.request, 'Tu contraseña fue cambiada.')
        return super().form_valid(form)


class Recuperar(_ConFormulario, acceso.PasswordResetView):
    form_class = RecuperarClaveForm
    email_template_name = 'correos/recuperar_clave.txt'
    subject_template_name = 'correos/recuperar_clave_asunto.txt'
    success_url = reverse_lazy('clientes:recuperar_enviado')
    extra_context = {
        'titulo': 'Recuperar contraseña',
        'intro': 'Escribe el correo de tu cuenta y te enviamos un enlace para poner una contraseña nueva.',
        'boton': 'Enviar enlace',
        'enlaces': [('clientes:entrar', 'Volver a iniciar sesión')],
    }

    def form_valid(self, form):
        # Un limite por conexion: nadie puede usar el formulario para llenar de correos a otra persona.
        ip = ip_del_cliente(self.request) or 'sin-ip'
        if services.bloqueado('recuperar', ip):
            form.add_error(None, 'Ya pediste varios enlaces. Espera 15 minutos.')
            return self.form_invalid(form)
        services.anotar_intento('recuperar', ip)
        return super().form_valid(form)


class RecuperarEnviado(acceso.PasswordResetDoneView):
    template_name = 'clientes/mensaje.html'
    extra_context = {
        'titulo': 'Revisa tu correo',
        'texto': 'Si hay una cuenta con ese correo, te enviamos un enlace para poner una contraseña nueva. '
                 'Puede tardar unos minutos; mira también la carpeta de spam.',
    }


class NuevaClave(_ConFormulario, acceso.PasswordResetConfirmView):
    form_class = NuevaClaveForm
    success_url = reverse_lazy('clientes:recuperar_listo')
    extra_context = {'titulo': 'Nueva contraseña', 'boton': 'Guardar contraseña'}


class RecuperarListo(acceso.PasswordResetCompleteView):
    template_name = 'clientes/mensaje.html'
    extra_context = {
        'titulo': 'Contraseña cambiada',
        'texto': 'Ya puedes iniciar sesión con tu contraseña nueva.',
        'enlace': ('clientes:entrar', 'Iniciar sesión'),
    }
