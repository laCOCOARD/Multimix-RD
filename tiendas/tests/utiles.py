from django.urls import reverse

from tiendas.models import Tienda

TIENDA_POR_DEFECTO = 'Multimix RD'


def tienda_de_prueba(nombre=TIENDA_POR_DEFECTO, con_cuenta=True, **datos):
    """Tienda con ese nombre; se crea la primera vez. Sin nombre es la tienda en la que corren casi todas las pruebas.

    Nace con una cuenta bancaria: cada tienda cobra en las suyas y sin una no ofrece transferencia (2026-10-26).
    """
    valores = {'prefijo': 'MMX', 'banner_titulo': 'Tu tienda de bienestar'} if nombre == TIENDA_POR_DEFECTO else {}
    # Sin ITBIS para que los totales de las pruebas sean los de los productos; el impuesto tiene las suyas.
    valores['itbis_porcentaje'] = 0
    valores.update(datos)
    tienda, creada = Tienda.objects.get_or_create(nombre=nombre, defaults=valores)
    if creada and con_cuenta:
        tienda.cuentas.create(banco='Banco de prueba', numero=f'000-{tienda.pk}', titular=nombre)
    return tienda


def ruta(nombre, *args, tienda=None):
    """`reverse` de una ruta que vive dentro de una tienda; por defecto, la tienda de prueba."""
    return reverse(nombre, args=[(tienda or tienda_de_prueba()).slug, *args])


def entrar_como_cliente(cliente, correo='cliente@example.com', nombre='Ana Pérez'):
    """Inicia sesion en el cliente de pruebas con una cuenta de cliente (se crea la primera vez): para comprar hace falta."""
    from django.contrib.auth import get_user_model

    from clientes.services import registrar_cliente

    usuario = get_user_model().objects.filter(username=correo).first()
    if usuario is None:
        usuario = registrar_cliente(nombre, correo, 'clave-de-prueba-123', '8095551234')
    cliente.force_login(usuario)
    return usuario
