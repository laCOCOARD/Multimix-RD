"""Videos de las tiendas: cuanto duran y en que formato vienen, sin programas externos.

El sitio no convierte videos (en Render free no hay ffmpeg ni memoria para hacerlo), asi que solo acepta lo que
reproducen todos los navegadores y telefonos: MP4 o MOV con la imagen en H.264 y el sonido en AAC (o sin sonido).
Se leen solo las cajas de cabecera del archivo (`moov` y, en los MP4 fragmentados, las `moof`), nunca el video
entero: lo demas se salta con `seek`.
"""
import struct
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ValidationError

EXTENSIONES_VIDEO = ('.mp4', '.m4v', '.mov')
MEGA = 1024 * 1024
# H.264 y AAC: los abre cualquier navegador. HEVC ("Alta eficiencia" del iPhone) no lo abren muchos Android.
IMAGEN_COMPATIBLE = {'avc1', 'avc3'}
SONIDO_COMPATIBLE = {'mp4a'}
HEVC = {'hvc1', 'hev1', 'dvh1', 'dvhe'}
# Un video de "15 segundos" del telefono suele durar unas decimas mas.
TOLERANCIA_SEGUNDOS = 0.5
# Una cabecera mas grande que esto no es de un video corto: no se lee a memoria.
MAXIMO_CABECERA = 32 * MEGA
MAXIMO_CAJAS = 20_000
# Las primeras cajas posibles de un MP4 (ftyp) o de un MOV antiguo, que puede empezar por cualquiera de estas.
PRIMERAS_CAJAS = {'ftyp', 'moov', 'mdat', 'wide', 'free', 'skip', 'pnot', 'uuid'}

DANADO = 'No pudimos leer el video: parece dañado o incompleto. Vuelve a exportarlo y súbelo otra vez.'
NO_ES_MP4 = 'El archivo no es un video MP4. Sube el video en MP4, el formato normal de los teléfonos.'
CONSEJO = 'Envíatelo por WhatsApp y sube el que te llega, o expórtalo desde CapCut en 720p.'


class VideoInvalido(ValueError):
    """El archivo no es un video que se pueda leer. El mensaje se puede mostrar tal cual."""


@dataclass(frozen=True)
class InfoVideo:
    duracion: float  # segundos
    imagen: str  # formato de la imagen: 'avc1' (H.264), 'hvc1' (HEVC)...
    sonido: str | None  # formato del sonido ('mp4a' = AAC), o None si no trae


def _cajas(datos, desde=0, hasta=None):
    """Las cajas dentro de un bloque ya leido: (tipo, inicio del contenido, fin)."""
    hasta = len(datos) if hasta is None else hasta
    posicion = desde
    while posicion + 8 <= hasta:
        tamano, tipo = struct.unpack_from('>I4s', datos, posicion)
        cabecera = 8
        if tamano == 1:
            tamano = struct.unpack_from('>Q', datos, posicion + 8)[0]
            cabecera = 16
        elif tamano == 0:
            tamano = hasta - posicion
        if tamano < cabecera or posicion + tamano > hasta:
            raise VideoInvalido(DANADO)
        yield tipo.decode('latin-1'), posicion + cabecera, posicion + tamano
        posicion += tamano


def _hija(datos, tipo, desde, hasta):
    """La primera caja de un tipo dentro de otra: (inicio, fin) o None."""
    return next(((inicio, fin) for nombre, inicio, fin in _cajas(datos, desde, hasta) if nombre == tipo), None)


def _cajas_del_archivo(archivo, total):
    """Las cajas de primer nivel del archivo, leyendo solo sus cabeceras: (tipo, inicio del contenido, largo)."""
    posicion = 0
    for _ in range(MAXIMO_CAJAS):
        if posicion + 8 > total:
            return
        archivo.seek(posicion)
        cabecera = archivo.read(16)
        if len(cabecera) < 8:
            return
        tamano, tipo = struct.unpack_from('>I4s', cabecera)
        tipo = tipo.decode('latin-1')
        if posicion == 0 and tipo not in PRIMERAS_CAJAS:
            # Una foto, un WebM o un documento con otro nombre: no es que este dañado.
            raise VideoInvalido(NO_ES_MP4)
        largo_cabecera = 8
        if tamano == 1:
            if len(cabecera) < 16:
                raise VideoInvalido(DANADO)
            tamano = struct.unpack_from('>Q', cabecera, 8)[0]
            largo_cabecera = 16
        elif tamano == 0:
            tamano = total - posicion
        if tamano < largo_cabecera or posicion + tamano > total:
            raise VideoInvalido(DANADO)
        yield tipo, posicion + largo_cabecera, tamano - largo_cabecera
        posicion += tamano
    raise VideoInvalido(DANADO)


def _escala_y_duracion(datos, inicio):
    """De `mvhd` o `mdhd`: unidades por segundo y duracion en esas unidades (0 si no la dice)."""
    if datos[inicio] == 1:
        escala, duracion = struct.unpack_from('>IQ', datos, inicio + 20)
        return escala, (0 if duracion == 0xFFFFFFFFFFFFFFFF else duracion)
    escala, duracion = struct.unpack_from('>II', datos, inicio + 12)
    return escala, (0 if duracion == 0xFFFFFFFF else duracion)


def _pista(datos, desde, hasta):
    """Lo que importa de una pista (`trak`): su numero, su escala de tiempo, si es imagen o sonido y su formato."""
    pista = {'id': None, 'escala': 0, 'duracion': 0, 'tipo': '', 'formato': ''}
    for tipo, inicio, fin in _cajas(datos, desde, hasta):
        if tipo == 'tkhd':
            pista['id'] = struct.unpack_from('>I', datos, inicio + (20 if datos[inicio] == 1 else 12))[0]
        elif tipo == 'mdia':
            for subtipo, sub_inicio, sub_fin in _cajas(datos, inicio, fin):
                if subtipo == 'mdhd':
                    pista['escala'], pista['duracion'] = _escala_y_duracion(datos, sub_inicio)
                elif subtipo == 'hdlr':
                    # En MP4 y en MOV el tipo ('vide', 'soun') va en la misma posicion.
                    pista['tipo'] = datos[sub_inicio + 8:sub_inicio + 12].decode('latin-1')
                elif subtipo == 'minf':
                    stbl = _hija(datos, 'stbl', sub_inicio, sub_fin)
                    stsd = _hija(datos, 'stsd', *stbl) if stbl else None
                    if stsd and stsd[0] + 16 <= stsd[1]:
                        pista['formato'] = datos[stsd[0] + 12:stsd[0] + 16].decode('latin-1')
    return pista


def _duracion_de_fragmentos(fragmentos, pista_id, por_defecto):
    """MP4 fragmentado (el de algunas apps y grabadoras): la suma de lo que dura cada muestra de la pista."""
    total = 0
    for moof in fragmentos:
        for tipo, inicio, fin in _cajas(moof):
            if tipo != 'traf':
                continue
            pista, duracion_base = None, por_defecto
            for subtipo, sub_inicio, sub_fin in _cajas(moof, inicio, fin):
                banderas = int.from_bytes(moof[sub_inicio + 1:sub_inicio + 4], 'big')
                if subtipo == 'tfhd':
                    pista = struct.unpack_from('>I', moof, sub_inicio + 4)[0]
                    posicion = sub_inicio + 8 + (8 if banderas & 0x01 else 0) + (4 if banderas & 0x02 else 0)
                    if banderas & 0x08:
                        duracion_base = struct.unpack_from('>I', moof, posicion)[0]
                elif subtipo == 'trun' and pista == pista_id:
                    muestras = struct.unpack_from('>I', moof, sub_inicio + 4)[0]
                    if not banderas & 0x100:
                        total += muestras * duracion_base
                        continue
                    posicion = sub_inicio + 8 + (4 if banderas & 0x01 else 0) + (4 if banderas & 0x04 else 0)
                    paso = 4 * sum(1 for bandera in (0x100, 0x200, 0x400, 0x800) if banderas & bandera)
                    if posicion + muestras * paso > sub_fin:
                        raise VideoInvalido(DANADO)
                    total += sum(struct.unpack_from('>I', moof, posicion + numero * paso)[0] for numero in range(muestras))
    return total


def leer_video(archivo):
    """Duracion y formatos de un MP4 o MOV. Lanza VideoInvalido si no es un video que se pueda leer."""
    try:
        archivo.seek(0, 2)
        total = archivo.tell()
        moov, fragmentos, leido = None, [], 0
        for tipo, inicio, largo in _cajas_del_archivo(archivo, total):
            if tipo in ('moov', 'moof'):
                leido += largo
                if leido > MAXIMO_CABECERA:
                    raise VideoInvalido(DANADO)
                archivo.seek(inicio)
                contenido = archivo.read(largo)
                if tipo == 'moov':
                    moov = contenido
                else:
                    fragmentos.append(contenido)
        if moov is None:
            raise VideoInvalido(NO_ES_MP4 if total < 8 else DANADO)

        escala, duracion = 0, 0
        pistas, por_defecto, fragmentada = [], {}, 0
        for tipo, inicio, fin in _cajas(moov):
            if tipo == 'mvhd':
                escala, duracion = _escala_y_duracion(moov, inicio)
            elif tipo == 'trak':
                pistas.append(_pista(moov, inicio, fin))
            elif tipo == 'mvex':
                for subtipo, sub_inicio, _fin in _cajas(moov, inicio, fin):
                    if subtipo == 'mehd':
                        fragmentada = struct.unpack_from('>Q' if moov[sub_inicio] == 1 else '>I', moov, sub_inicio + 4)[0]
                    elif subtipo == 'trex':
                        pista_id, _, duracion_muestra = struct.unpack_from('>III', moov, sub_inicio + 4)
                        por_defecto[pista_id] = duracion_muestra

        imagen = next((pista for pista in pistas if pista['tipo'] == 'vide'), None)
        if imagen is None:
            raise VideoInvalido('El archivo no trae imagen de video. Sube un video MP4.')
        sonido = next((pista['formato'] for pista in pistas if pista['tipo'] == 'soun'), None)

        if escala and duracion:
            segundos = duracion / escala
        elif escala and fragmentada:
            segundos = fragmentada / escala
        elif imagen['escala'] and imagen['duracion']:
            segundos = imagen['duracion'] / imagen['escala']
        elif imagen['escala'] and fragmentos:
            segundos = _duracion_de_fragmentos(fragmentos, imagen['id'], por_defecto.get(imagen['id'], 0)) / imagen['escala']
        else:
            raise VideoInvalido(DANADO)
    except (struct.error, IndexError) as error:
        raise VideoInvalido(DANADO) from error
    finally:
        archivo.seek(0)
    return InfoVideo(duracion=round(segundos, 2), imagen=imagen['formato'], sonido=sonido)


def _megas(cantidad):
    return f'{cantidad / MEGA:.1f}'.removesuffix('.0')


def validar_video(archivo):
    """Para el campo del video: MP4 o MOV en H.264 (y AAC), dentro del peso y la duracion de la configuracion.

    Un video ya guardado no se vuelve a revisar: seria descargarlo del almacenamiento cada vez que se edita el resto.
    """
    from core.models import ConfiguracionTienda

    if getattr(archivo, '_committed', False):
        return
    config = ConfiguracionTienda.obtener()
    if Path(archivo.name).suffix.lower() not in EXTENSIONES_VIDEO:
        raise ValidationError(NO_ES_MP4)
    if archivo.size > config.video_megas_maximos * MEGA:
        raise ValidationError(
            f'El video pesa {_megas(archivo.size)} MB y el máximo es {config.video_megas_maximos} MB. {CONSEJO}'
        )
    try:
        info = leer_video(archivo)
    except VideoInvalido as error:
        raise ValidationError(str(error)) from error
    if info.imagen in HEVC:
        raise ValidationError(
            'El video está en HEVC (la "Alta eficiencia" del iPhone), que muchos teléfonos Android no reproducen. '
            f'{CONSEJO} En el iPhone también puedes grabar en "Más compatible" (Ajustes > Cámara > Formatos).'
        )
    if info.imagen not in IMAGEN_COMPATIBLE:
        raise ValidationError(
            f'La imagen del video viene en un formato ({info.imagen or "desconocido"}) que no todos los teléfonos '
            f'reproducen. {CONSEJO}'
        )
    if info.sonido and info.sonido not in SONIDO_COMPATIBLE:
        raise ValidationError(
            f'El sonido del video viene en un formato ({info.sonido}) que no todos los teléfonos reproducen. {CONSEJO}'
        )
    if info.duracion < 1:
        raise ValidationError('El video es demasiado corto: tiene que durar al menos 1 segundo.')
    if info.duracion > config.video_segundos_maximos + TOLERANCIA_SEGUNDOS:
        raise ValidationError(
            f'El video dura {round(info.duracion)} segundos y el máximo es {config.video_segundos_maximos}. '
            'Recórtalo y súbelo otra vez.'
        )
