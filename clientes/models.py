from django.conf import settings
from django.db import models


class Perfil(models.Model):
    """Datos del cliente que no estan en su usuario: el telefono y sus preferencias. Las direcciones van aparte
    (`Direccion`).

    La cuenta es del sitio, no de una tienda: el mismo cliente compra en todas. La zona de envio no se
    guarda porque cada tienda tiene las suyas.
    """

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    telefono = models.CharField('teléfono', max_length=10, blank=True)
    # Abrio el enlace que se le envio al correo (o el de recuperar la contraseña): el correo es suyo.
    correo_verificado = models.BooleanField('correo confirmado', default=False)
    recordatorios = models.BooleanField(
        'recibir recordatorios del carrito', default=True,
        help_text='Un correo si deja productos en el carrito sin comprar.',
    )
    # Lo que contesto al crear su cuenta (pedido del dueño el 2026-10-27; ver clientes/gustos.py): ordena las promociones,
    # el buscador y las categorias, y elige la entrega del checkout. Las cambia o las borra en "Mi cuenta".
    gustos = models.JSONField('gustos', default=dict, blank=True)
    # Se le preguntan una sola vez, justo despues de crear la cuenta.
    preguntar_gustos = models.BooleanField(default=False, editable=False)

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


class Direccion(models.Model):
    """Direccion de entrega guardada: el cliente elige una en el checkout en vez de escribirla otra vez."""

    MAXIMO = 10

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='direcciones')
    nombre = models.CharField(max_length=40, help_text='Ej.: Casa, Trabajo, Casa de mamá.')
    sector = models.CharField(max_length=80)
    direccion = models.CharField('calle y número', max_length=255)
    referencia = models.CharField('referencia', max_length=255, blank=True)
    principal = models.BooleanField(default=False, help_text='La que llega puesta en el checkout.')
    creado = models.DateTimeField(auto_now_add=True)
    usada = models.DateTimeField('última vez usada', null=True, blank=True)

    class Meta:
        verbose_name = 'dirección'
        verbose_name_plural = 'direcciones'
        ordering = ['-principal', '-usada', '-id']

    def __str__(self):
        return f'{self.nombre}: {self.direccion}, {self.sector}'


class CarritoGuardado(models.Model):
    """Copia del carrito de la sesion en la cuenta: se recupera al entrar desde otro equipo y permite recordarle
    al cliente lo que dejo sin comprar. Mismo formato que la sesion: {id_tienda: {'items': ..., 'cupon': ...}}."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='carrito_guardado')
    datos = models.JSONField(default=dict)
    actualizado = models.DateTimeField()
    recordado = models.DateTimeField('recordatorio enviado', null=True, blank=True)

    class Meta:
        verbose_name = 'carrito guardado'
        verbose_name_plural = 'carritos guardados'

    def __str__(self):
        return f'Carrito de {self.usuario_id}'
