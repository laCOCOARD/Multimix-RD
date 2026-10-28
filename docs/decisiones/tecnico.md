# Detalles tecnicos y particularidades de Django

Decisiones tomadas en Multimix RD (movidas desde CLAUDE.md el 2026-10-28). Leelas antes de tocar esta parte del proyecto.

- Sin cron en Render free: `config.middleware.TareasPeriodicasMiddleware` llama a `core.tareas.ejecutar_si_toca`,
  que como mucho una vez por hora (candado en la cache) cancela los pedidos vencidos y borra sesiones caducadas.
  En las pruebas esta apagado (`TAREAS_AUTOMATICAS`).
- Imagenes: `validar_imagen` mide los pixeles leyendo solo la cabecera (`IMAGEN_MAX_PIXELES` 40 MP;
  `IMAGEN_MAX_PIXELES_JPEG` 120 MP, porque un JPG se abre reducido con `draft`). `convertir_a_webp` achica antes de
  girar segun el EXIF, para no tener dos copias grandes en memoria (Render free tiene 512 MB).
- Correos: `core.correo.enviar` (texto, plantillas en `templates/correos/`, nunca lanza: registra el fallo) y
  `pedidos.avisos` (pedido nuevo, cambio de estado, comprobante, pago rechazado). Salen con
  `transaction.on_commit`, asi que en las pruebas hay que envolver con `captureOnCommitCallbacks(execute=True)`.
  En produccion van por la API de Brevo (`BREVO_API_KEY`, `core.correo_brevo.BrevoBackend`): Render free bloquea
  SMTP y el envio se quedaba en `TimeoutError`. Con `EMAIL_HOST` van por SMTP y sin nada, a la consola. La tienda recibe en su correo de
  contacto y, si no tiene, en el de sus vendedores, el del sitio o el de los superusuarios. Los enlaces usan
  `SITIO_URL`. En Configuracion general hay un boton "Enviar correo de prueba" (Render free no tiene consola).
- Proyecto en `C:\Users\elies\multimix_rd` (no en la carpeta de usuario) para aislar el repositorio.
- Paquete de configuracion: `config`. Apps en la raiz del proyecto.
- `django-import-export[xlsx]`: el extra instala openpyxl, necesario para Excel.
- SQLite usa `transaction_mode=IMMEDIATE` para serializar escrituras (alli `select_for_update` no hace nada).
- ConfiguracionTienda: `save()` fuerza `pk=1`, `delete()` no hace nada, `obtener()` la entrega con cache.
  Guarda lo del sitio (nombre, logo, descripcion, contactos, dias de "nuevo", umbral de stock, horas de
  vencimiento); el banner, la direccion para recoger y el contra entrega son de cada `Tienda`.
- `Tienda` repite los nombres de campo de contacto de ConfiguracionTienda (`nombre`, `logo`, `whatsapp`,
  redes...) y expone `descripcion` (su `banner_subtitulo`). En las plantillas `tienda` es la subtienda actual
  (o nada en las paginas del sitio), `plataforma` la configuracion y `marca` la que firme la pagina
  (`tienda or plataforma`).
- Los ModelAdmin con imagenes heredan `core.admin_avisos.AvisaImagenesSinGuardar`: si el formulario vuelve
  con errores, el navegador olvida los archivos elegidos y hay que avisarlo.
  El mismo mixin atrapa los fallos del almacenamiento (`core.archivos.ERRORES_DE_ALMACENAMIENTO`) y vuelve
  al formulario con un mensaje en vez de un error 500.
- Las imagenes se guardan con nombre generado: `core.archivos.NombreUnico('carpeta')` como `upload_to`
  (logo y banner de tienda, logo del sitio, categorias) y uuid en `FotoProducto.save`. Supabase responde 400
  a los nombres con tildes o ñ. Por eso el almacenamiento va con `file_overwrite=True` (no pregunta si el
  archivo existe): una imagen nueva nunca debe guardarse con el nombre que trae del usuario.
- Supabase lento: botocore con 5 s de conexion, 20 s de lectura y 2 intentos (`client_config`), y
  `gunicorn.conf.py` con `timeout = 120`. Con los valores por defecto Gunicorn mataba la peticion a los 30 s.
- Rutas de tienda bajo `/tienda/<tienda_slug>/` (`tiendas.decoradores.RUTA_DE_TIENDA`). `pedidos` y `core`
  mezclan rutas de tienda y del sitio, por eso declaran las suyas completas y se incluyen en la raiz.
  Las paginas por token (confirmacion, factura) ponen `request.tienda = pedido.tienda`.
- Las tiendas las crea el superusuario. Al asignar usuarios en `TiendaAdmin` se llama
  `dar_acceso_al_panel` (personal + grupo Vendedores); `tienda.usuarios.add()` a secas no da permisos.
  El grupo y sus permisos (`PERMISOS_VENDEDOR`) se crean con `post_migrate`.
- El campo `tienda` de los formularios del panel nunca se excluye: va oculto (vendedor con una tienda) o
  deshabilitado (al editar). Si se excluyera, Django no validaria las unicidades por tienda (SKU, slug,
  codigo de cupon, zona) y fallaria con IntegrityError.
- `Tienda.prefijo` no cambia despues de crear la tienda: ya esta en los numeros de pedido emitidos.
- `/catalogo/`, `/producto/<slug>/`, `/carrito/`... (de cuando habia una tienda) redirigen a la tienda mas
  antigua activa (`tiendas.services.tienda_principal`).
- Migracion a subtiendas en tres pasos por app (campo opcional, datos, campo obligatorio) y en archivos
  separados: PostgreSQL no deja alterar una tabla en la misma transaccion en que se actualizaron sus filas.
  `tiendas/0002` crea la primera tienda (prefijo MMX) solo si ya habia configuracion o datos.
- Al agrupar (`annotate` con Count/Sum) Django ignora el `ordering` del modelo: se ordena a mano.
- En los tests la cache es `DummyCache` para que cada prueba sea independiente.
- Telefonos guardados como 10 digitos (`8095551234`); para wa.me se antepone `1`.
- `PanelAdminConfig` vive en `config/apps.py` (no en `core/apps.py`: Django no admite dos AppConfig por
  defecto en un modulo). El sitio es `core.admin_site.PanelAdminSite`; el resumen sale de `core/panel.py`.
- `core/migrations/0002` quita de la configuracion el logo o banner cuyo archivo ya no existe en el
  almacenamiento (se perdieron los que se subieron cuando los archivos iban al disco de Render).
- Acciones del admin: las descripciones pasan por formato `%`, asi que un `%` literal se escribe `%%`.
- `docs/esquema.sql` se genera con `sqlmigrate` sobre SQLite; regenerarlo si cambian las migraciones.
