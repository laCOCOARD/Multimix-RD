from django.conf import settings
from django.db import models


class Perfil(models.Model):
    """Datos del cliente que no estan en su usuario: el telefono y la ultima direccion a la que pidio.

    La cuenta es del sitio, no de una tienda: el mismo cliente compra en todas. La zona de envio no se
    guarda aqui porque cada tienda tiene las suyas.
    """

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    telefono = models.CharField('teléfono', max_length=10, blank=True)
    sector = models.CharField(max_length=80, blank=True)
    direccion = models.CharField('calle y número', max_length=255, blank=True)
    referencia = models.CharField('referencia de la dirección', max_length=255, blank=True)

    class Meta:
        verbose_name = 'perfil de cliente'
        verbose_name_plural = 'perfiles de clientes'

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.get_username()


class Favorito(models.Model):
    """Producto que el cliente guardo para volver a encontrarlo."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favoritos')
    producto = models.ForeignKey('catalogo.Producto', on_delete=models.CASCADE, related_name='favoritos')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'favorito'
        verbose_name_plural = 'favoritos'
        ordering = ['-creado', '-id']
        constraints = [models.UniqueConstraint(fields=['usuario', 'producto'], name='favorito_unico_por_cliente')]

    def __str__(self):
        return f'{self.usuario_id} · {self.producto_id}'
