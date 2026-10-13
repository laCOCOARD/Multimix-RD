"""Pasarelas de pago con tarjeta. Aun no hay ninguna activa: falta la afiliacion del comercio.

La tienda no depende de una pasarela concreta. Cada proveedor (AZUL, CardNET...) sera una clase que
herede de `ProveedorDePago`, se registre con `registrar` y se elija con la variable de entorno
`PAGOS_PROVEEDOR_TARJETA`. Sus credenciales van siempre en variables de entorno, nunca en el codigo ni
en la base de datos. Ver docs/PAGOS.md.
"""
from dataclasses import dataclass

from django.conf import settings


@dataclass
class Resultado:
    """Lo que un proveedor informa de un cobro, ya verificado contra el proveedor."""

    aprobado: bool
    referencia: str  # la referencia de nuestro Pago, tal como se le envio al proveedor
    codigo_autorizacion: str = ''
    mensaje: str = ''
    datos: dict | None = None  # respuesta sin datos de tarjeta, para conciliar


class ProveedorDePago:
    """Contrato que cumple cada pasarela."""

    codigo = ''
    nombre = ''

    def configurado(self):
        """True si estan todas las credenciales del comercio en el entorno."""
        raise NotImplementedError

    def iniciar(self, pago, url_retorno, url_cancelacion):
        """Devuelve a donde enviar al cliente para pagar (URL y campos del formulario del proveedor)."""
        raise NotImplementedError

    def verificar(self, datos):
        """Comprueba la respuesta o notificacion del proveedor (firma incluida) y devuelve un `Resultado`.

        Debe poder recibir la misma notificacion varias veces: `pagos.services.aprobar_pago` no cobra dos veces.
        """
        raise NotImplementedError

    def reembolsar(self, pago, monto):
        raise NotImplementedError


_PROVEEDORES = {}


def registrar(clase):
    _PROVEEDORES[clase.codigo] = clase
    return clase


def proveedor_de_tarjeta():
    """La pasarela elegida y lista para cobrar, o None. Mientras sea None, la tienda no ofrece tarjeta."""
    clase = _PROVEEDORES.get(getattr(settings, 'PAGOS_PROVEEDOR_TARJETA', ''))
    if clase is None:
        return None
    proveedor = clase()
    return proveedor if proveedor.configurado() else None
