import logging

from django.contrib import messages
from django.shortcuts import redirect

from .archivos import ERRORES_DE_ALMACENAMIENTO

registro = logging.getLogger(__name__)


class AvisaImagenesSinGuardar:
    """Para ModelAdmin con campos de imagen. Va antes de ModelAdmin en la herencia.

    Cuando un formulario vuelve con errores, el navegador olvida los archivos que se habian elegido.
    Sin este aviso, quien corrige el error y guarda cree que sus imagenes se subieron.

    Y si el almacenamiento de las fotos falla o tarda demasiado, en vez de una pagina de error se
    vuelve al formulario diciendo que no se guardo nada.
    """

    aviso_imagenes = (
        'Las imágenes que elegiste todavía no se guardaron porque hay errores en el formulario. '
        'Corrígelos y vuelve a elegir las imágenes antes de guardar.'
    )
    aviso_almacenamiento = (
        'No se pudo guardar la imagen: el almacenamiento de fotos no respondió. No se guardó ningún cambio. '
        'Espera un momento, vuelve a elegir las imágenes e inténtalo otra vez.'
    )

    def render_change_form(self, request, context, *args, **kwargs):
        if request.method == 'POST' and request.FILES and context.get('errors'):
            self.message_user(request, self.aviso_imagenes, messages.WARNING)
        return super().render_change_form(request, context, *args, **kwargs)

    def changeform_view(self, request, *args, **kwargs):
        if request.method != 'POST' or not request.FILES:
            return super().changeform_view(request, *args, **kwargs)
        try:
            # La vista corre en una transaccion: si el almacenamiento falla, no queda nada a medias.
            return super().changeform_view(request, *args, **kwargs)
        except ERRORES_DE_ALMACENAMIENTO:
            registro.exception('No se pudo guardar una imagen desde el panel')
            self.message_user(request, self.aviso_almacenamiento, messages.ERROR)
            return redirect(request.get_full_path())
