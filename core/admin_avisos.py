from django.contrib import messages


class AvisaImagenesSinGuardar:
    """Para ModelAdmin con campos de imagen. Va antes de ModelAdmin en la herencia.

    Cuando un formulario vuelve con errores, el navegador olvida los archivos que se habian elegido.
    Sin este aviso, quien corrige el error y guarda cree que sus imagenes se subieron.
    """

    aviso_imagenes = (
        'Las imágenes que elegiste todavía no se guardaron porque hay errores en el formulario. '
        'Corrígelos y vuelve a elegir las imágenes antes de guardar.'
    )

    def render_change_form(self, request, context, *args, **kwargs):
        if request.method == 'POST' and request.FILES and context.get('errors'):
            self.message_user(request, self.aviso_imagenes, messages.WARNING)
        return super().render_change_form(request, context, *args, **kwargs)
