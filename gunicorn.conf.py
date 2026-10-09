"""Gunicorn lee este archivo solo al arrancar desde la raiz del proyecto."""

# Por defecto son 30 s. Subir una imagen pasa por el almacenamiento de fotos (hasta 5 MB por archivo y
# dos intentos de 25 s cada uno): con 30 s Gunicorn cortaba la peticion antes de poder avisar del fallo.
timeout = 120
