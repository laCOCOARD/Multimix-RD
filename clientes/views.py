from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as acceso
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
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


@login_not_required
@sensitive_post_parameters('clave', 'clave_repetida')
@never_cache
def registro(request):
    if request.user.is_authenticated:
        return redirect('clientes:cuenta')
    ip = ip_del_cliente(request)
    formulario = RegistroForm(request.POST or None)
    if request.method == 'POST':
        if services.registro_bloqueado(ip):
            formulario.add_error(None, 'Se crearon varias cuentas desde tu conexión. Espera unos minutos.')
        elif formulario.is_valid():
            services.anotar_registro(ip)
            usuario = formulario.save()
            login(request, usuario, backend='clientes.autenticacion.CorreoOUsuarioBackend')
            if services.correo_confirmado(usuario):
                messages.success(request, f'¡Bienvenido, {usuario.first_name}! Tu cuenta ya está creada.')
            else:
                services.enviar_confirmacion(usuario)
                messages.success(
                    request, f'¡Bienvenido, {usuario.first_name}! Te enviamos un enlace a {usuario.email} para '
                             'confirmar tu correo antes de tu primera compra.',
                )
            return redirect(_destino(request))
    return render(request, PLANTILLA, {
        'formulario': formulario,
        'titulo': 'Crear cuenta',
        'intro': ('Crea tu cuenta en un minuto para terminar tu compra. Tu carrito te espera.'
                  if '/pedido/checkout/' in _destino(request, '') else
                  'Con tu cuenta ves tus pedidos, no escribes tus datos en cada compra y los avisos te llegan a tu correo.'),
        'aviso_legal': True,
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
        'intro': 'Entra para comprar, seguir tus pedidos y guardar tus favoritos.',
        'boton': 'Entrar',
        'enlaces': [
            ('clientes:registro', '¿No tienes cuenta? Créala gratis'),
            ('clientes:recuperar', 'Olvidé mi contraseña'),
        ],
    }

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        siguiente = _destino(self.request, '')
        contexto.update(formulario=contexto['form'], siguiente=siguiente)
        if '/pedido/checkout/' in siguiente:
            # Viene del carrito: el carrito se conserva al entrar o al crear la cuenta.
            contexto['intro'] = 'Inicia sesión para terminar tu compra. Tu carrito te espera.'
        return contexto


class Salir(acceso.LogoutView):
    next_page = reverse_lazy('clientes:entrar')


@login_not_required
@never_cache
def confirmar_correo(request, token):
    """El enlace del correo de confirmacion."""
    usuario = services.confirmar_correo(token)
    if usuario is None:
        return render(request, 'clientes/mensaje.html', {
            'titulo': 'Enlace vencido',
            'texto': 'Este enlace ya no vale. Entra a tu cuenta y pide uno nuevo.',
            'enlace': ('clientes:confirma_tu_correo', 'Pedir otro enlace'),
            'icono': 'bi-envelope-exclamation text-warning',
        })
    messages.success(request, 'Listo, confirmamos tu correo. Ya puedes comprar.')
    if request.user.is_authenticated and request.user.pk == usuario.pk:
        return redirect('clientes:cuenta')
    return redirect('clientes:entrar')


@login_required
@never_cache
def confirma_tu_correo(request):
    """Antes de comprar: el correo de la cuenta todavia no esta confirmado. Aqui se reenvia el enlace."""
    if services.correo_confirmado(request.user):
        return redirect(_destino(request))
    if request.method == 'POST':
        if services.enviar_confirmacion(request.user):
            messages.success(request, f'Te enviamos un enlace nuevo a {request.user.email}.')
        else:
            messages.error(request, 'Ya te enviamos varios enlaces. Revisa tu correo (y la carpeta de spam) o espera una hora.')
        siguiente = _destino(request, '')
        return redirect(f"{request.path}?{urlencode({'next': siguiente})}" if siguiente else request.path)
    return render(request, 'clientes/confirmar_correo.html', {'siguiente': _destino(request, '')})


@login_required
def cuenta(request):
    """Los pedidos del cliente en todas las tiendas. Solo los suyos."""
    pedidos = Pedido.objects.filter(cliente=request.user).select_related('tienda').order_by('-creado', '-id')
    return render(request, 'clientes/cuenta.html', {
        'pagina': Paginator(pedidos, PEDIDOS_POR_PAGINA).get_page(request.GET.get('pagina')),
        'perfil': services.perfil_de(request.user),
        'correo_confirmado': services.correo_confirmado(request.user),
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
        # Un limite por conexion y otro por correo: nadie puede usar el formulario para llenar de correos a otra
        # persona, aunque cambie de IP. Pasado el del correo se responde igual, sin enviar, para no revelar nada.
        ip = ip_del_cliente(self.request)
        if services.recuperacion_bloqueada(ip):
            form.add_error(None, 'Ya pediste varios enlaces. Espera 15 minutos.')
            return self.form_invalid(form)
        services.anotar_recuperacion(ip)
        if not services.puede_recibir_enlace(form.cleaned_data['email']):
            return redirect(self.get_success_url())
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

    def form_valid(self, form):
        # El enlace llego a su correo: eso tambien lo confirma.
        services.marcar_correo_confirmado(form.user)
        return super().form_valid(form)


class RecuperarListo(acceso.PasswordResetCompleteView):
    template_name = 'clientes/mensaje.html'
    extra_context = {
        'titulo': 'Contraseña cambiada',
        'texto': 'Ya puedes iniciar sesión con tu contraseña nueva.',
        'enlace': ('clientes:entrar', 'Iniciar sesión'),
    }
