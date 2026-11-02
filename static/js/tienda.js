/* Comportamiento comun de la tienda: animaciones, avisos y "agregar al carrito" sin recargar. */
(() => {
  'use strict';

  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /** Envia un formulario por POST con fetch. Devuelve el JSON del servidor. */
  async function enviar(url, datos) {
    const respuesta = await fetch(url, {
      method: 'POST',
      body: datos,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': datos.get('csrfmiddlewaretoken') || '' },
    });
    const tipo = respuesta.headers.get('content-type') || '';
    if (!tipo.includes('application/json')) throw new Error('Respuesta inesperada del servidor');
    return respuesta.json();
  }

  /** Aviso breve abajo de la pantalla. `enlace` ({texto, url}) agrega un enlace al final. Se arma con nodos: el
   *  texto viene del servidor, pero nunca se trata como HTML. */
  function avisar(mensaje, tipo = 'exito', enlace = null) {
    const contenedor = document.getElementById('avisos');
    if (!mensaje || !contenedor || !window.bootstrap) return;
    const colores = { exito: 'text-bg-success', error: 'text-bg-danger', aviso: 'text-bg-warning' };
    const toast = document.createElement('div');
    toast.className = `toast align-items-center border-0 ${colores[tipo] || colores.exito}`;
    toast.setAttribute('role', 'status');
    const fila = document.createElement('div');
    fila.className = 'd-flex';
    const cuerpo = document.createElement('div');
    cuerpo.className = 'toast-body';
    cuerpo.textContent = mensaje;
    if (enlace) {
      const ir = document.createElement('a');
      ir.className = 'mm-aviso-enlace';
      ir.href = enlace.url;
      ir.textContent = enlace.texto;
      cuerpo.append(' ', ir);
    }
    const cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.className = `btn-close ${tipo === 'aviso' ? '' : 'btn-close-white '}me-2 m-auto`;
    cerrar.setAttribute('data-bs-dismiss', 'toast');
    cerrar.setAttribute('aria-label', 'Cerrar');
    fila.append(cuerpo, cerrar);
    toast.appendChild(fila);
    contenedor.appendChild(toast);
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    new bootstrap.Toast(toast, { delay: enlace ? 6000 : 3500 }).show();
  }

  function actualizarContador(cantidad) {
    document.querySelectorAll('.js-contador-carrito').forEach((contador) => {
      contador.textContent = cantidad;
      contador.classList.toggle('d-none', !cantidad);
      contador.classList.remove('mm-salto', 'mm-salto-dorado');
      void contador.offsetWidth;
      // Si hay producto nuevo: rebote dorado; si se vacia: rebote simple.
      contador.classList.add(cantidad ? 'mm-salto-dorado' : 'mm-salto');
    });
  }

  /** Confetti: rectangulitos de colores que caen desde arriba. */
  function _confetti() {
    const canvas = document.createElement('canvas');
    canvas.className = 'mm-confetti-canvas';
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    document.body.appendChild(canvas);
    const ctx2 = canvas.getContext('2d');
    const COLORES = ['#F59E0B','#10B981','#3B82F6','#EF4444','#8B5CF6','#EC4899','#06B6D4','#F97316'];
    const piezas = Array.from({ length: 130 }, () => ({
      x: Math.random() * canvas.width,
      y: -20 - Math.random() * 120,
      vx: (Math.random() - 0.5) * 4,
      vy: 2.5 + Math.random() * 3.5,
      w: 7 + Math.random() * 6,
      h: 4 + Math.random() * 4,
      a: Math.random() * Math.PI * 2,
      va: (Math.random() - 0.5) * 0.18,
      color: COLORES[Math.floor(Math.random() * COLORES.length)],
      op: 1,
    }));
    let activo = true;
    let raf;
    (function tick() {
      ctx2.clearRect(0, 0, canvas.width, canvas.height);
      let vivos = 0;
      piezas.forEach((p) => {
        if (p.y > canvas.height + 20) return;
        vivos++;
        p.x += p.vx; p.y += p.vy; p.vy += 0.06; p.a += p.va;
        if (p.y > canvas.height * 0.72) p.op = Math.max(0, p.op - 0.025);
        ctx2.save();
        ctx2.translate(p.x, p.y);
        ctx2.rotate(p.a);
        ctx2.globalAlpha = p.op;
        ctx2.fillStyle = p.color;
        ctx2.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx2.restore();
      });
      if (vivos > 0 && activo) raf = requestAnimationFrame(tick);
      else canvas.remove();
    })();
    return () => { activo = false; cancelAnimationFrame(raf); setTimeout(() => canvas.remove(), 50); };
  }

  /** Fanfarria de trompeta con Web Audio API. */
  function _trompeta() {
    try {
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      // G4-G4-G4-E5-C5-E5-G5 (ta-ta-ta-DUM)
      const notas = [392, 392, 392, 659.25, 523.25, 659.25, 783.99];
      const dur =   [0.12, 0.12, 0.12,  0.32,    0.18,    0.18,  0.42];
      const pausas = [0.05, 0.05, 0.08,  0.04,    0.04,    0.04,   0];
      let t = ac.currentTime + 0.05;
      notas.forEach((freq, i) => {
        const d = dur[i];
        const osc1 = ac.createOscillator();
        const osc2 = ac.createOscillator();
        const filtro = ac.createBiquadFilter();
        const gain = ac.createGain();
        osc1.type = 'sawtooth'; osc1.frequency.value = freq;
        osc2.type = 'square';   osc2.frequency.value = freq * 2;
        filtro.type = 'lowpass';
        filtro.frequency.setValueAtTime(600, t);
        filtro.frequency.exponentialRampToValueAtTime(3500, t + 0.04);
        osc1.connect(filtro); osc2.connect(filtro); filtro.connect(gain); gain.connect(ac.destination);
        gain.gain.setValueAtTime(0, t);
        gain.gain.linearRampToValueAtTime(0.1, t + 0.018);
        gain.gain.setValueAtTime(0.1, t + d - 0.03);
        gain.gain.linearRampToValueAtTime(0, t + d);
        osc1.start(t); osc1.stop(t + d);
        osc2.start(t); osc2.stop(t + d);
        t += d + pausas[i];
      });
    } catch (e) {}
  }

  /** Confetti solo en tonos dorados: para la victoria del checkout. */
  function _confettiDorado() {
    const canvas = document.createElement('canvas');
    canvas.className = 'mm-confetti-canvas';
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    document.body.appendChild(canvas);
    const ctx2 = canvas.getContext('2d');
    const COLORES = ['#F59E0B', '#FFD04A', '#FFF7C0', '#D97706', '#FEF3C7', '#ffffff', '#111827'];
    const piezas = Array.from({ length: 90 }, () => ({
      x: Math.random() * canvas.width,
      y: -20 - Math.random() * 80,
      vx: (Math.random() - 0.5) * 3,
      vy: 2 + Math.random() * 3,
      w: 5 + Math.random() * 8,
      h: 3 + Math.random() * 4,
      a: Math.random() * Math.PI * 2,
      va: (Math.random() - 0.5) * 0.13,
      color: COLORES[Math.floor(Math.random() * COLORES.length)],
      op: 1,
    }));
    let activo = true;
    let raf;
    (function tick() {
      ctx2.clearRect(0, 0, canvas.width, canvas.height);
      let vivos = 0;
      piezas.forEach((p) => {
        if (p.y > canvas.height + 20) return;
        vivos++;
        p.x += p.vx; p.y += p.vy; p.vy += 0.055; p.a += p.va;
        if (p.y > canvas.height * 0.75) p.op = Math.max(0, p.op - 0.02);
        ctx2.save();
        ctx2.translate(p.x, p.y);
        ctx2.rotate(p.a);
        ctx2.globalAlpha = p.op;
        ctx2.fillStyle = p.color;
        ctx2.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx2.restore();
      });
      if (vivos > 0 && activo) raf = requestAnimationFrame(tick);
      else canvas.remove();
    })();
    return () => { activo = false; cancelAnimationFrame(raf); setTimeout(() => canvas.remove(), 50); };
  }

  /** Cuatro notas ascendentes suaves: la victoria tranquila del checkout. */
  function _sonarVictoria() {
    try {
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      [[523.25, 0, .14], [659.25, .13, .13], [783.99, .26, .15], [1046.5, .40, .36]]
        .forEach(([freq, delay, dur]) => {
          const o = ac.createOscillator();
          const g = ac.createGain();
          o.connect(g); g.connect(ac.destination);
          o.type = 'sine';
          o.frequency.setValueAtTime(freq, ac.currentTime + delay);
          g.gain.setValueAtTime(0, ac.currentTime + delay);
          g.gain.linearRampToValueAtTime(0.14, ac.currentTime + delay + .03);
          g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + delay + dur);
          o.start(ac.currentTime + delay);
          o.stop(ac.currentTime + delay + dur + .05);
        });
    } catch (e) {}
  }

  /** Victoria al confirmar un pedido: confetti dorado + sonido suave. Una sola vez por sesion. */
  function celebrarPedido(token) {
    if (sinMovimiento) return;
    const key = `mm-v-${token}`;
    try { if (sessionStorage.getItem(key)) return; } catch (e) {}
    try { sessionStorage.setItem(key, '1'); } catch (e) {}
    _sonarVictoria();
    _confettiDorado();
    document.querySelector('.mm-numero-pedido')?.classList.add('mm-numero-pedido-victoria');
  }

  /** Celebración cuando un cupón meta se aplica automáticamente al carrito.
   *  `datos` = { codigo, antes_raw, despues_raw, descuento_texto, url_guardar }
   *  `cb`    = { onAplicar, onGuardar } */
  function celebrarCupon(datos, cb = {}) {
    if (!datos) return;
    if (sinMovimiento) {
      avisar(`¡Cupón ${datos.codigo} aplicado! Ahorras ${datos.descuento_texto}.`, 'exito');
      cb.onAplicar?.();
      return;
    }

    _trompeta();
    document.querySelector('.mm-celebracion')?.remove();
    document.querySelector('.mm-confetti-canvas')?.remove();
    const pararConfetti = _confetti();

    const ANIMAR_MS = 1000;
    const fmt = (n) => 'RD$ ' + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

    // Estructura del modal (todo innerHTML es estático sin datos del usuario).
    const nodo = document.createElement('div');
    nodo.className = 'mm-celebracion';
    nodo.setAttribute('role', 'dialog');
    nodo.setAttribute('aria-modal', 'true');
    nodo.setAttribute('aria-label', '¡Cupón aplicado!');
    nodo.innerHTML = [
      '<div class="mm-celebracion-fondo" aria-hidden="true"></div>',
      '<div class="mm-celebracion-panel">',
      '  <div class="mm-celebracion-icono"><i class="bi bi-gift-fill" aria-hidden="true"></i></div>',
      '  <div class="mm-celebracion-titulo"></div>',
      '  <div class="mm-celebracion-codigo"></div>',
      '  <div class="mm-celebracion-monto">',
      '    <span class="mm-celebracion-antes"></span>',
      '    <span class="mm-celebracion-flecha"><i class="bi bi-arrow-right-short" aria-hidden="true"></i></span>',
      '    <span class="mm-celebracion-despues"></span>',
      '  </div>',
      '  <div class="mm-celebracion-ahorro"></div>',
      '  <div class="mm-celebracion-botones">',
      '    <button class="mm-celebracion-aplicar" type="button"></button>',
      '    <button class="mm-celebracion-guardar" type="button"></button>',
      '  </div>',
      '</div>',
    ].join('');

    // Relleno seguro con textContent.
    nodo.querySelector('.mm-celebracion-titulo').textContent = '¡Felicidades! Descuento aplicado';
    nodo.querySelector('.mm-celebracion-codigo').textContent = `Cupón ${datos.codigo}`;

    const antesEl = nodo.querySelector('.mm-celebracion-antes');
    antesEl.textContent = fmt(datos.antes_raw);

    const despuesEl = nodo.querySelector('.mm-celebracion-despues');
    despuesEl.textContent = fmt(datos.antes_raw);

    const ahorroEl = nodo.querySelector('.mm-celebracion-ahorro');
    const tagIcon = document.createElement('i');
    tagIcon.className = 'bi bi-tag-fill me-1';
    tagIcon.setAttribute('aria-hidden', 'true');
    ahorroEl.append(tagIcon, `Ahorras ${datos.descuento_texto}`);

    nodo.querySelector('.mm-celebracion-aplicar').textContent = '¡Usar descuento ahora!';
    nodo.querySelector('.mm-celebracion-guardar').textContent = 'Guardar para otra compra';

    document.body.appendChild(nodo);
    requestAnimationFrame(() => requestAnimationFrame(() => nodo.classList.add('visible')));

    // Animar precio.
    setTimeout(() => {
      const inicio = performance.now();
      const desde = datos.antes_raw;
      const hasta = datos.despues_raw;
      (function tick(ahora) {
        const p = Math.min((ahora - inicio) / ANIMAR_MS, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        despuesEl.textContent = fmt(desde + (hasta - desde) * ease);
        if (p < 1) requestAnimationFrame(tick);
      })(performance.now());
    }, 300);

    const cerrar = (accion) => {
      nodo.classList.remove('visible');
      pararConfetti();
      setTimeout(() => nodo.remove(), 400);
      if (accion === 'aplicar') cb.onAplicar?.();
      else cb.onGuardar?.();
    };

    nodo.querySelector('.mm-celebracion-aplicar').addEventListener('click', () => cerrar('aplicar'));
    nodo.querySelector('.mm-celebracion-guardar').addEventListener('click', () => cerrar('guardar'));
    nodo.querySelector('.mm-celebracion-fondo').addEventListener('click', () => cerrar('aplicar'));
  }

  window.Multimix = { enviar, avisar, actualizarContador, celebrarCupon, celebrarPedido };

  // Promociones de la portada: rotan solas (se detienen al pasar el raton o con "reducir movimiento").
  document.querySelectorAll('.js-promos').forEach((carrusel) => {
    if (!window.bootstrap) return;
    new bootstrap.Carousel(carrusel, {
      interval: sinMovimiento ? false : 5500, ride: sinMovimiento ? false : 'carousel', pause: 'hover', touch: true,
    });
  });

  // Un formulario que vuelve con errores lleva el foco a su resumen (se lee primero y enlaza a cada campo).
  const resumenDeErrores = document.querySelector('.mm-errores[tabindex]');
  if (resumenDeErrores) resumenDeErrores.focus();

  // Aparicion al deslizar. Cada grupo entra con su estilo y, si entran varios a la vez, en cascada.
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const animar = (selector, ...clases) => document.querySelectorAll(selector).forEach((nodo) => nodo.classList.add('revelar', ...clases));
  animar('.mm-seccion-cabecera, .mm-legal-cabecera, main h1:not(.mm-hero-titulo):not(.mm-banner-titulo)', 'revelar-izq');
  animar('.mm-burbuja', 'revelar-zoom');
  animar('.mm-vender, .mm-llamado, .mm-filtros, .mm-panel, .mm-legal-indice');
  // Categorias y tiendas solo aparecen, sin moverse: van en filas que se deslizan (o no, segun el ancho) y un
  // desplazamiento las sacaria de la fila o de la pagina mientras esperan a verse.
  animar('.mm-fila .mm-categoria, .mm-fila .mm-anuncio, .mm-fila .mm-historia, .mm-tienda', 'revelar-suave');
  document.querySelectorAll('.mm-fila .mm-tarjeta').forEach((tarjeta) => tarjeta.classList.add('revelar-der'));

  const elementos = document.querySelectorAll('.revelar');
  if ('IntersectionObserver' in window && !quieto) {
    const observador = new IntersectionObserver((entradas) => {
      const nuevas = entradas.filter((entrada) => entrada.isIntersecting)
        .sort((a, b) => (a.boundingClientRect.top - b.boundingClientRect.top) || (a.boundingClientRect.left - b.boundingClientRect.left));
      nuevas.forEach((entrada, orden) => {
        const nodo = entrada.target;
        nodo.style.setProperty('--retraso', `${Math.min(orden, 7) * 70}ms`);
        nodo.classList.add('visible');
        observador.unobserve(nodo);
        // Ya en su sitio, sin retraso: el efecto al pasar el raton responde al instante.
        setTimeout(() => nodo.style.removeProperty('--retraso'), 1200);
      });
    }, { rootMargin: '0px 0px -40px 0px', threshold: 0.05 });
    elementos.forEach((elemento) => observador.observe(elemento));
  } else {
    elementos.forEach((elemento) => elemento.classList.add('visible'));
  }

  // Al deslizar: barra de progreso, cabecera con sombra, boton para volver arriba y el banner de la tienda mas lento.
  const progreso = document.querySelector('.mm-progreso');
  const cabecera = document.querySelector('.mm-cabecera');
  const arriba = document.querySelector('.mm-arriba');
  const capas = quieto ? [] : Array.from(document.querySelectorAll('.mm-banner .container'));
  let pendiente = false;
  const alDeslizar = () => {
    pendiente = false;
    const y = window.scrollY;
    const alto = document.documentElement.scrollHeight - window.innerHeight;
    if (progreso) progreso.style.transform = `scaleX(${alto > 0 ? Math.min(1, y / alto) : 0})`;
    if (cabecera) cabecera.classList.toggle('con-sombra', y > 8);
    if (arriba) arriba.classList.toggle('visible', y > 700);
    capas.forEach((capa) => {
      const caja = capa.parentElement.getBoundingClientRect();
      if (caja.bottom < 0) return;
      capa.style.transform = `translateY(${Math.max(0, -caja.top) * 0.3}px)`;
      capa.style.opacity = String(Math.max(0.2, 1 - Math.max(0, -caja.top) / caja.height));
    });
  };
  window.addEventListener('scroll', () => {
    if (!pendiente) { pendiente = true; requestAnimationFrame(alDeslizar); }
  }, { passive: true });
  alDeslizar();
  if (arriba) arriba.addEventListener('click', () => window.scrollTo({ top: 0, behavior: quieto ? 'auto' : 'smooth' }));

  // Agregar al carrito sin recargar. Si algo falla, el formulario se envia de la forma normal.
  document.addEventListener('submit', async (evento) => {
    const formulario = evento.target.closest('form.js-agregar');
    if (!formulario) return;
    if (!formulario.checkValidity()) return;
    // "Comprar ahora" lleva al checkout: se envia de la forma normal.
    if (evento.submitter && evento.submitter.name === 'comprar') return;
    evento.preventDefault();
    const boton = evento.submitter || formulario.querySelector('[type="submit"]');
    const htmlOriginal = boton.innerHTML;
    const soloIcono = 'soloIcono' in boton.dataset;
    boton.disabled = true;
    boton.innerHTML = soloIcono
      ? '<span class="mm-spinner" aria-hidden="true"></span>'
      : '<span class="mm-spinner" aria-hidden="true"></span><span class="mm-spinner-texto">Agregando…</span>';
    try {
      const datos = await enviar(formulario.action, new FormData(formulario));
      // En el carrito, lo agregado desde las sugerencias tiene que verse en las lineas y el total.
      if (datos.ok && document.querySelector('[data-recargar-al-agregar]')) {
        window.location.reload();
        return;
      }
      actualizarContador(datos.cantidad_total);
      if (datos.cupon_meta_auto) {
        const meta = datos.cupon_meta_auto;
        celebrarCupon(meta, {
          onAplicar: () => {},
          onGuardar: async () => {
            const fd = new FormData();
            fd.append('codigo', meta.codigo);
            await enviar(meta.url_guardar, fd).catch(() => {});
          },
        });
      }
      // Fuera de una tienda (portada, buscador del sitio, favoritos) no hay carrito en la cabecera: el aviso
      // enlaza al carrito de la tienda del producto, que es la carpeta anterior de /carrito/agregar/.
      const sinCarritoALaVista = !document.querySelector('.js-contador-carrito');
      const enlace = datos.ok && sinCarritoALaVista
        ? { texto: formulario.dataset.tienda ? `Ver carrito de ${formulario.dataset.tienda}` : 'Ver carrito', url: new URL('../', formulario.action).href }
        : null;
      avisar(datos.mensaje, datos.ok ? 'exito' : 'error', enlace);
      if (datos.ok && boton) {
        // El boton confirma por un momento que el producto ya esta en el carrito.
        boton.innerHTML = soloIcono ? '<i class="bi bi-check-lg"></i>' : '<i class="bi bi-check-lg me-1"></i>Agregado';
        boton.classList.add('mm-agregado');
        setTimeout(() => { boton.innerHTML = htmlOriginal; boton.classList.remove('mm-agregado'); }, 1600);
      } else if (boton) {
        boton.innerHTML = htmlOriginal;
      }
    } catch (error) {
      formulario.classList.remove('js-agregar');
      formulario.submit();
      return;
    }
    boton.disabled = false;
  });

  // Corazon de las tarjetas: guarda o quita el favorito sin recargar. Si algo falla, se envia de la forma normal.
  document.addEventListener('submit', async (evento) => {
    const formulario = evento.target.closest('form.js-favorito');
    if (!formulario) return;
    evento.preventDefault();
    const boton = formulario.querySelector('button');
    boton.disabled = true;
    try {
      const datos = await enviar(formulario.action, new FormData(formulario));
      const guardado = Boolean(datos.favorito);
      boton.classList.toggle('activo', guardado);
      boton.setAttribute('aria-pressed', String(guardado));
      boton.title = guardado ? 'Quitar de favoritos' : 'Guardar en favoritos';
      boton.setAttribute('aria-label', boton.getAttribute('aria-label').replace(guardado ? /^Guardar (.*) en favoritos$/ : /^Quitar (.*) de favoritos$/, guardado ? 'Quitar $1 de favoritos' : 'Guardar $1 en favoritos'));
      boton.firstElementChild.className = guardado ? 'bi bi-heart-fill' : 'bi bi-heart';
      avisar(datos.mensaje, 'exito', guardado ? { texto: 'Ver favoritos', url: formulario.dataset.favoritos } : null);
    } catch (error) {
      formulario.classList.remove('js-favorito');
      formulario.submit();
      return;
    }
    boton.disabled = false;
  });

  // Compartir un producto: el menu del telefono si existe; si no, copia el enlace.
  document.querySelectorAll('.js-compartir').forEach((boton) => {
    boton.addEventListener('click', async () => {
      const datos = { title: boton.dataset.titulo, url: boton.dataset.url };
      try {
        if (navigator.share) {
          await navigator.share(datos);
        } else {
          await navigator.clipboard.writeText(datos.url);
          avisar('Enlace copiado. Pégalo donde quieras compartirlo.');
        }
      } catch (error) {
        if (error.name !== 'AbortError') avisar('No se pudo compartir. Copia el enlace de la barra de direcciones.', 'aviso');
      }
    });
  });

  // Buscador con sugerencias. Sin JavaScript sigue siendo un formulario normal.
  document.querySelectorAll('form.js-buscador').forEach((formulario) => {
    const campo = formulario.querySelector('input[name="q"]');
    const origen = formulario.dataset.sugerencias;
    if (!campo || !origen) return;

    const lista = document.createElement('ul');
    lista.className = 'mm-sugerencias';
    lista.id = `sugerencias-${Math.random().toString(36).slice(2, 8)}`;
    lista.setAttribute('role', 'listbox');
    lista.hidden = true;
    formulario.appendChild(lista);
    campo.setAttribute('role', 'combobox');
    campo.setAttribute('aria-autocomplete', 'list');
    campo.setAttribute('aria-controls', lista.id);
    campo.setAttribute('aria-expanded', 'false');

    let espera = null;
    let pedido = 0;
    let activa = -1;

    const opciones = () => Array.from(lista.querySelectorAll('a'));
    const cerrar = () => {
      lista.hidden = true;
      activa = -1;
      campo.setAttribute('aria-expanded', 'false');
      campo.removeAttribute('aria-activedescendant');
    };
    const marcar = (indice) => {
      const enlaces = opciones();
      if (!enlaces.length) return;
      activa = (indice + enlaces.length) % enlaces.length;
      enlaces.forEach((enlace, i) => enlace.classList.toggle('activa', i === activa));
      campo.setAttribute('aria-activedescendant', enlaces[activa].id);
    };

    const fila = (hijo, clase = '') => {
      const item = document.createElement('li');
      item.setAttribute('role', clase ? 'presentation' : 'none');
      if (clase) item.className = clase;
      item.appendChild(hijo);
      return item;
    };
    const aviso = (texto, clase) => {
      const nodo = document.createElement('span');
      nodo.textContent = texto;
      return fila(nodo, clase);
    };
    const opcion = (resultado, indice, detalleTexto, esTienda) => {
      const enlace = document.createElement('a');
      enlace.href = resultado.url;
      enlace.id = `${lista.id}-${indice}`;
      enlace.setAttribute('role', 'option');
      if (resultado.foto) {
        const foto = document.createElement('img');
        foto.src = resultado.foto;
        foto.alt = '';
        foto.width = 44;
        foto.height = 44;
        enlace.appendChild(foto);
      } else if (esTienda) {
        const inicial = document.createElement('span');
        inicial.className = 'mm-sugerencia-inicial';
        inicial.setAttribute('aria-hidden', 'true');
        inicial.textContent = resultado.nombre.slice(0, 1).toUpperCase();
        enlace.appendChild(inicial);
      }
      const cuerpo = document.createElement('span');
      cuerpo.className = 'mm-sugerencia-cuerpo';
      const nombre = document.createElement('span');
      nombre.className = 'mm-sugerencia-nombre';
      nombre.textContent = resultado.nombre;
      const detalle = document.createElement('span');
      detalle.className = 'mm-sugerencia-detalle';
      detalle.textContent = detalleTexto;
      cuerpo.append(nombre, detalle);
      enlace.appendChild(cuerpo);
      return fila(enlace);
    };
    const todos = (texto, etiqueta) => {
      const enlace = document.createElement('a');
      enlace.href = `${formulario.action}?q=${encodeURIComponent(texto)}`;
      enlace.id = `${lista.id}-todos`;
      enlace.className = 'mm-sugerencia-todos';
      enlace.setAttribute('role', 'option');
      enlace.textContent = etiqueta;
      return fila(enlace);
    };
    const abrir = () => {
      activa = -1;
      lista.hidden = false;
      campo.setAttribute('aria-expanded', 'true');
    };

    // Mientras llega la respuesta: "Buscando...". Se ve solo si tarda (no parpadea en las respuestas rapidas).
    let avisoDeCarga = null;
    function mostrarCargando(texto) {
      clearTimeout(avisoDeCarga);
      avisoDeCarga = setTimeout(() => {
        lista.replaceChildren(aviso(`Buscando «${texto}»…`, 'mm-sugerencia-estado'));
        abrir();
      }, 250);
    }

    function pintar(resultados, texto, tiendas = []) {
      clearTimeout(avisoDeCarga);
      lista.replaceChildren();
      if (tiendas.length) {
        lista.appendChild(aviso('Tiendas', 'mm-sugerencia-grupo'));
        tiendas.forEach((resultado, i) => lista.appendChild(opcion(resultado, `t${i}`, resultado.detalle, true)));
      }
      if (resultados.length) {
        if (tiendas.length) lista.appendChild(aviso('Productos', 'mm-sugerencia-grupo'));
        resultados.forEach((resultado, i) => {
          lista.appendChild(opcion(resultado, i, resultado.tienda ? `${resultado.precio} · ${resultado.tienda}` : resultado.precio));
        });
      }
      if (resultados.length || tiendas.length) {
        lista.appendChild(todos(texto, `Ver todos los resultados de «${texto}»`));
      } else {
        // Sin resultados: se dice y se ofrece buscar igual (la pagina de resultados sugiere otros productos).
        lista.appendChild(aviso(`No encontramos nada para «${texto}».`, 'mm-sugerencia-estado'));
        lista.appendChild(todos(texto, 'Buscar de todos modos'));
      }
      abrir();
    }

    async function buscar() {
      const texto = campo.value.trim();
      // Vacio o una sola letra: no se busca nada.
      if (texto.length < 2) { clearTimeout(avisoDeCarga); cerrar(); return; }
      const turno = ++pedido;
      mostrarCargando(texto);
      try {
        const respuesta = await fetch(`${origen}?q=${encodeURIComponent(texto)}`, { credentials: 'same-origin' });
        if (!respuesta.ok) throw new Error('sin sugerencias');
        const datos = await respuesta.json();
        // Solo se pinta la respuesta de lo ultimo que se escribio.
        if (turno === pedido) pintar(datos.resultados || [], texto, datos.tiendas || []);
      } catch (error) {
        if (turno === pedido) { clearTimeout(avisoDeCarga); cerrar(); }
      }
    }

    campo.addEventListener('input', () => {
      clearTimeout(espera);
      espera = setTimeout(buscar, 220);
    });
    campo.addEventListener('keydown', (evento) => {
      if (lista.hidden) return;
      if (evento.key === 'ArrowDown') { evento.preventDefault(); marcar(activa + 1); }
      else if (evento.key === 'ArrowUp') { evento.preventDefault(); marcar(activa - 1); }
      else if (evento.key === 'Escape') { cerrar(); }
      else if (evento.key === 'Enter' && activa >= 0) { evento.preventDefault(); opciones()[activa].click(); }
    });
    document.addEventListener('click', (evento) => {
      if (!formulario.contains(evento.target)) cerrar();
    });
  });

  // Galeria del producto: las fotos se deslizan con el dedo (scroll-snap) y las miniaturas llevan a cada una.
  const pistaGaleria = document.querySelector('.js-galeria-pista');
  if (pistaGaleria) {
    const miniaturas = Array.from(document.querySelectorAll('.js-miniatura'));
    const puntos = Array.from(document.querySelectorAll('.js-galeria-puntos span'));
    const marcar = (indice) => {
      miniaturas.forEach((miniatura, i) => miniatura.classList.toggle('activa', i === indice));
      puntos.forEach((punto, i) => punto.classList.toggle('activo', i === indice));
    };
    const irA = (indice) => pistaGaleria.scrollTo({
      left: indice * pistaGaleria.clientWidth, behavior: sinMovimiento ? 'auto' : 'smooth',
    });
    miniaturas.forEach((miniatura, indice) => {
      miniatura.addEventListener('click', (evento) => {
        evento.preventDefault();
        irA(indice);
        marcar(indice);
      });
    });
    let espera;
    pistaGaleria.addEventListener('scroll', () => {
      clearTimeout(espera);
      espera = setTimeout(() => marcar(Math.round(pistaGaleria.scrollLeft / pistaGaleria.clientWidth)), 60);
    }, { passive: true });
    pistaGaleria.addEventListener('keydown', (evento) => {
      const actual = Math.round(pistaGaleria.scrollLeft / pistaGaleria.clientWidth);
      if (evento.key === 'ArrowRight') { evento.preventDefault(); irA(Math.min(actual + 1, miniaturas.length - 1)); }
      if (evento.key === 'ArrowLeft') { evento.preventDefault(); irA(Math.max(actual - 1, 0)); }
    });
  }

  // Filas que se deslizan: flechas en pantallas con raton y, con data-auto, avance solo cada pocos segundos.
  document.querySelectorAll('[data-fila]').forEach((fila) => {
    const pista = fila.querySelector('.mm-fila-pista');
    const anterior = fila.querySelector('[data-mover="-1"]');
    const siguiente = fila.querySelector('[data-mover="1"]');
    if (!pista) return;

    const uno = () => {
      const item = pista.querySelector('.mm-fila-item');
      return item ? item.getBoundingClientRect().width + (parseFloat(getComputedStyle(pista).columnGap) || 0) : pista.clientWidth;
    };
    // Las flechas avanzan las tarjetas que se ven completas, al menos una.
    const paso = () => Math.max(uno(), Math.floor(pista.clientWidth / uno()) * uno());
    const alFinal = () => pista.scrollLeft + pista.clientWidth >= pista.scrollWidth - 4;
    const actualizar = () => {
      const desborda = pista.scrollWidth > pista.clientWidth + 4;
      [anterior, siguiente].forEach((boton) => { if (boton) boton.hidden = !desborda; });
      if (anterior) anterior.disabled = pista.scrollLeft <= 4;
      if (siguiente) siguiente.disabled = alFinal();
    };
    const mover = (direccion) => pista.scrollBy({ left: direccion * paso(), behavior: sinMovimiento ? 'auto' : 'smooth' });

    [anterior, siguiente].forEach((boton) => {
      if (boton) boton.addEventListener('click', () => mover(Number(boton.dataset.mover)));
    });
    pista.addEventListener('scroll', actualizar, { passive: true });
    window.addEventListener('resize', actualizar);
    actualizar();

    if (fila.hasAttribute('data-auto') && !sinMovimiento) {
      let pausa = false;
      ['mouseenter', 'focusin', 'touchstart'].forEach((evento) => fila.addEventListener(evento, () => { pausa = true; }, { passive: true }));
      ['mouseleave', 'focusout'].forEach((evento) => fila.addEventListener(evento, () => { pausa = false; }));
      setInterval(() => {
        if (pausa || document.hidden || pista.scrollWidth <= pista.clientWidth + 4) return;
        // Solo avanza si la fila esta a la vista; al llegar al final vuelve al comienzo.
        const caja = fila.getBoundingClientRect();
        if (caja.bottom < 0 || caja.top > window.innerHeight) return;
        if (alFinal()) pista.scrollTo({ left: 0, behavior: 'smooth' });
        else pista.scrollBy({ left: uno(), behavior: 'smooth' });
      }, 4500);
    }
  });

  // Cuenta regresiva de las ofertas que terminan pronto.
  document.querySelectorAll('.mm-cuenta-atras[data-fin]').forEach((nodo) => {
    const fin = new Date(nodo.dataset.fin).getTime();
    const tiempo = nodo.querySelector('.js-tiempo');
    if (!tiempo || Number.isNaN(fin)) return;
    const dos = (n) => String(n).padStart(2, '0');
    const pintar = () => {
      const resta = Math.max(0, Math.floor((fin - Date.now()) / 1000));
      if (!resta) { tiempo.textContent = 'hoy'; return false; }
      const dias = Math.floor(resta / 86400);
      const reloj = `${dos(Math.floor(resta / 3600) % 24)}:${dos(Math.floor(resta / 60) % 60)}:${dos(resta % 60)}`;
      tiempo.textContent = `en ${dias ? `${dias} d ` : ''}${reloj}`;
      return true;
    };
    if (pintar()) {
      const reloj = setInterval(() => { if (!pintar()) clearInterval(reloj); }, 1000);
    }
  });

  // Barra de compra fija: aparece cuando el boton principal ya quedo arriba.
  const compraFija = document.querySelector('.mm-compra-fija');
  const formCompra = document.getElementById('form-compra');
  if (compraFija && formCompra && 'IntersectionObserver' in window) {
    new IntersectionObserver(([entrada]) => {
      const mostrar = !entrada.isIntersecting && entrada.boundingClientRect.top < 0;
      compraFija.classList.toggle('visible', mostrar);
      compraFija.setAttribute('aria-hidden', String(!mostrar));
      compraFija.querySelectorAll('button').forEach((boton) => { boton.tabIndex = mostrar ? 0 : -1; });
    }).observe(formCompra);
  }

  // Foto que no carga (archivo borrado del almacenamiento): se cambia por el icono de "sin foto".
  document.addEventListener('error', (evento) => {
    const foto = evento.target;
    if (!(foto instanceof HTMLImageElement) || !foto.closest('.mm-tarjeta-foto, .mm-galeria-principal, .mm-linea-foto')) return;
    const vacio = document.createElement('span');
    vacio.className = 'mm-sin-foto';
    vacio.innerHTML = '<i class="bi bi-image"></i><span>Sin foto</span>';
    foto.replaceWith(vacio);
  }, true);

  // Barra del telefono: "Buscar" sube al buscador de la cabecera y lo deja listo para escribir. Sin JavaScript abre
  // la pagina de busqueda (o el catalogo de la tienda).
  document.querySelectorAll('.js-ir-al-buscador').forEach((enlace) => {
    enlace.addEventListener('click', (evento) => {
      const campo = document.querySelector('.mm-cabecera .mm-buscador-campo');
      if (!campo) return;
      evento.preventDefault();
      window.scrollTo(0, 0);
      campo.focus();
    });
  });

  // Botones que piden confirmacion antes de enviar (cancelar un pedido). Sin JavaScript el formulario se envia igual.
  document.addEventListener('click', (evento) => {
    const boton = evento.target.closest('[data-confirmar]');
    if (boton && !window.confirm(boton.dataset.confirmar)) evento.preventDefault();
  });

  // Ojo para mostrar/ocultar la contraseña en los campos de clave.
  document.querySelectorAll('.js-ver-clave').forEach((boton) => {
    const grupo = boton.closest('.mm-clave-grupo');
    const campo = grupo && grupo.querySelector('input');
    if (!campo) return;
    boton.addEventListener('click', () => {
      const mostrar = campo.type === 'password';
      campo.type = mostrar ? 'text' : 'password';
      boton.querySelector('i').className = mostrar ? 'bi bi-eye-slash' : 'bi bi-eye';
      boton.setAttribute('aria-label', mostrar ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  });

  // App instalable: el service worker guarda los estaticos y da la pagina "Sin conexion" sin internet.
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  // Boton "Instalar la app" del menu: aparece cuando el navegador ofrece instalarla (Android, Chrome, Edge).
  const seccionInstalar = document.querySelector('.mm-instalar');
  const yaInstalada = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  if (seccionInstalar && !yaInstalada) {
    const botonInstalar = seccionInstalar.querySelector('.js-instalar');
    let ofrecimiento = null;
    window.addEventListener('beforeinstallprompt', (evento) => {
      evento.preventDefault();
      ofrecimiento = evento;
      seccionInstalar.hidden = false;
      botonInstalar.hidden = false;
    });
    botonInstalar.addEventListener('click', async () => {
      if (!ofrecimiento) return;
      ofrecimiento.prompt();
      await ofrecimiento.userChoice;
      ofrecimiento = null;
      seccionInstalar.hidden = true;
    });
    window.addEventListener('appinstalled', () => { seccionInstalar.hidden = true; });
    // Safari del iPhone no ofrece instalar: se explica el camino de Compartir > Agregar a inicio.
    const esIphone = /iphone|ipad|ipod/i.test(navigator.userAgent);
    if (esIphone) {
      seccionInstalar.hidden = false;
      seccionInstalar.querySelector('.js-instalar-ios').hidden = false;
    }
  }

  // Victoria al llegar a la confirmacion de un pedido: lee el token del data-attribute.
  const panelVictoria = document.querySelector('[data-pedido-victoria]');
  if (panelVictoria) celebrarPedido(panelVictoria.dataset.pedidoVictoria);

  // Lupa en la foto del producto: con el raton, la foto que se ve se amplia donde apunta.
  const marco = document.querySelector('.mm-galeria-principal');
  if (marco && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    marco.addEventListener('mousemove', (evento) => {
      const pista = marco.querySelector('.js-galeria-pista');
      const indice = pista ? Math.round(pista.scrollLeft / pista.clientWidth) : 0;
      const foto = marco.querySelectorAll('img')[indice];
      if (!foto) return;
      const caja = marco.getBoundingClientRect();
      foto.style.transformOrigin = `${((evento.clientX - caja.left) / caja.width) * 100}% ${((evento.clientY - caja.top) / caja.height) * 100}%`;
      marco.classList.add('ampliada');
    });
    marco.addEventListener('mouseleave', () => marco.classList.remove('ampliada'));
  }
})();
