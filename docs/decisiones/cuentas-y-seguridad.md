# Cuentas, acceso y seguridad

Decisiones tomadas en Multimix RD (movidas desde CLAUDE.md el 2026-10-28). Leelas antes de tocar esta parte del proyecto.

- La pagina del pedido lleva `<meta name="referrer" content="same-origin">`, nunca `no-referrer`: con este ultimo
  el navegador envia `Origin: null` en sus formularios (comprobante, cancelar, devolucion) y Django responde 403.
  Paso en produccion y las pruebas no lo ven, porque el cliente de pruebas no manda `Origin`.
- Cabecera CSP (`POLITICA_DE_CONTENIDO` en settings): scripts y estilos solo del sitio y de cdn.jsdelivr.net. Los
  scripts SIN 'unsafe-inline': nada de `<script>` sin `src` ni `onclick=` en las plantillas (lo comprueba
  `core/test_seguridad.py`); va en `static/js/` (`panel.js` en el panel, `tienda.js`, `js-activo.js`). Los botones
  que piden confirmacion llevan `data-confirmar`. Los estilos si llevan 'unsafe-inline' (atributos `style`). El
  JSON-LD (`application/ld+json`) no se ejecuta y no lo afecta. `form-action 'self'`: al conectar una pasarela
  que reciba un formulario hay que agregar su dominio.
- `/salud/` responde "ok" si la aplicacion y la base funcionan (para el Health Check Path de Render).
- Entrar: `clientes.autenticacion.CorreoOUsuarioBackend` acepta el usuario o el correo (si es de una sola cuenta):
  el superusuario de Render es `MULTIMIX_ADMIN` y el formulario del sitio pide el correo. Ojo: el arranque de
  Render vuelve a poner la contraseña del superusuario desde `DJANGO_SUPERUSER_PASSWORD` en cada despliegue, asi
  que recuperarla por correo dura hasta el siguiente. `BrevoBackend` registra cada envio aceptado con su messageId.
- Cuentas de clientes: son usuarios de Django sin acceso al panel, con el correo como nombre de usuario, y son
  del sitio, no de una tienda (`/cuenta/`). `clientes.Perfil` guarda el telefono y si quiere recordatorios; las
  direcciones son `clientes.Direccion` (hasta 10, una principal que llega puesta en el checkout; cada pedido a
  domicilio guarda la suya si es nueva; `clientes/0006` paso la del perfil). La zona no, porque es de cada tienda.
  Con la sesion iniciada el carrito tambien se copia a `clientes.CarritoGuardado` (en `Carrito._guardar`; el
  personal del panel no) y vuelve a la sesion al entrar (`carrito.carrito.recuperar_al_entrar`, senal
  `user_logged_in`; lo de la sesion manda). Las tareas periodicas envian un recordatorio a quien lo dejo entre 1 y 7
  dias (uno por cada vez que lo deja; enlace firmado para apagarlos). "Volver a pedir" (`pedidos:volver_a_pedir`,
  por token) pone en el carrito lo del pedido que siga a la venta. `Pedido.cliente` solo se llena si compro con la sesion iniciada: un pedido
  de invitado (de antes de la cuenta obligatoria) nunca se asocia despues a una cuenta por coincidir el correo. Las plantillas de acceso estan en `templates/clientes/` y no en
  `templates/registration/`, que pisaria las pantallas de contraseña del panel.
- Limite de intentos (`core.limites`, filas `core.Intento` con la clave en sha256; las viejas las borran las
  tareas periodicas): vive en la base, no en la cache, para que lo compartan los procesos y no se borre al
  reiniciar. La IP no es fiable, asi que lo que importa cuenta tambien sin ella (`clientes.services`): entrar, 5
  por conexion y correo y 10 por cuenta desde cualquier IP, y el panel (`EntrarAlPanelForm`, `PanelAdminSite.
  login_form`) cuenta junto con el sitio; cuentas nuevas, 5 por conexion y 30 en todo el sitio; enlaces de
  recuperacion o confirmacion, 3 por hora a un mismo correo (pasado el limite responde igual, sin enviar);
  pedidos, `PEDIDOS_MAX_POR_CUENTA`; cupones que no aplican (`promociones.services.probar_cupon`, desde
  `Carrito.aplicar_cupon`), 10 por cuenta, sesion o IP y 100 por tienda, sin contar dos veces el mismo codigo.
- IP del visitante (`core.red.ip_del_cliente`): solo la cabecera que el proxy reescribe (`settings.CABECERA_IP`:
  `CF-Connecting-IP` en Render, que va detras de Cloudflare; `X-Real-IP` con Nginx). Nunca la primera de
  `X-Forwarded-For`: Render la deja como la mando el visitante y se podia inventar una IP en cada intento. Sin la
  cabecera devuelve None (no hay limite por IP) y lo registra una vez.
- Correo confirmado (`clientes.Perfil.correo_verificado`): al crear la cuenta se envia un enlace firmado
  (`signing`, 3 dias, ligado al correo); el checkout lo exige (`correo_confirmado`) y manda a
  `/cuenta/confirmar/`. Recuperar la contraseña tambien lo confirma. Las cuentas anteriores quedaron confirmadas
  (`clientes/0004`); el personal del panel no lo necesita. Apagado sin correo configurado y en las pruebas
  (`VERIFICAR_CORREO`).
- WhatsApp siempre con codigo de pais: `core.telefonos.normalizar_whatsapp` antepone el 1 a los numeros
  dominicanos de 10 digitos. Se aplica al validar y guardar Tienda y ConfiguracionTienda y, por si acaso, al
  armar cada enlace (`construir_enlace`). Sin el 1, wa.me abre un numero de otro pais.
- Cuenta para comprar: se navega y se arma el carrito sin cuenta (Google ve el catalogo); el checkout lleva
  `@login_required` y el carrito ofrece "Iniciar sesion y continuar" (el carrito de la sesion se conserva al
  entrar). El dueño pidio primero cerrar todo el sitio y despues, el 2026-10-14, abrirlo: el cierre sigue
  disponible con la variable `CUENTA_OBLIGATORIA=1` (`config.middleware.CuentaObligatoriaMiddleware`, el
  `LoginRequiredMiddleware` de Django), que manda a `/cuenta/entrar/` todo el sitio. Abren sin sesion, con
  `@login_not_required`: entrar, crear cuenta, recuperar contraseña, terminos, politicas, preguntas, robots,
  sitemap, `/salud/`, el panel (se protege solo) y las paginas por token del pedido (los enlaces de los correos y
  los pedidos de invitado anteriores). Una vista nueva del sitio queda cerrada sin hacer nada. En las pruebas esta
  apagado (`CUENTA_OBLIGATORIA`); `clientes/tests/test_cuenta_obligatoria.py` lo prueba encendido. Sin sesion la
  plantilla oculta menu, buscador y carrito (`puede_navegar`). El checkout lleva ademas `@login_required`.
- Gustos del cliente (pedido del dueño el 2026-10-27; `clientes/gustos.py`, `Perfil.gustos`): al crear la cuenta, una
  sola vez (`Perfil.preguntar_gustos`), cuatro preguntas de seleccion (categorias del sitio, que busca, presupuesto,
  entrega) en `/cuenta/gustos/`, con "Ahora no" que sigue a donde iba. Se usan para ordenar promociones, categorias de
  la portada y el buscador sin orden elegido, y para marcar la entrega del checkout; se cambian o borran desde "Mi
  cuenta". La politica de privacidad lo dice (`core/0024`). No se comparten con las tiendas.
