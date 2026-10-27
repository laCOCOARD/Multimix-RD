/* Videos de las tiendas (plan Premium): visor como las historias de Instagram o los estados de WhatsApp.
 *
 * Un grupo por tienda. Los videos pasan solos y al terminar los de una tienda sigue la siguiente. Tocar a la
 * izquierda vuelve, a la derecha avanza y dejar el dedo puesto pausa. El video solo se descarga cuando alguien lo
 * abre. Sin JavaScript (o en un navegador sin <dialog>) cada circulo abre el video tal cual.
 * Los datos salen de includes/visor_historias.html y se ponen con textContent: nunca como HTML. */
(() => {
  'use strict';

  const datos = document.getElementById('mm-historias-datos');
  const visor = document.getElementById('mm-visor');
  if (!datos || !visor || typeof visor.showModal !== 'function') return;

  const grupos = Array.from(datos.querySelectorAll('.js-historia-grupo')).map((grupo) => ({
    nombre: grupo.dataset.nombre || '',
    url: grupo.dataset.url || '#',
    logo: grupo.dataset.logo || '',
    videos: Array.from(grupo.querySelectorAll('.js-historia-video')).map((video) => ({
      id: video.dataset.id,
      src: video.dataset.src,
      titulo: video.dataset.titulo || '',
      producto: video.dataset.producto || '',
      vista: video.dataset.vista || '',
    })),
  }));
  if (!grupos.some((grupo) => grupo.videos.length)) return;

  const $ = (selector) => visor.querySelector(selector);
  const video = $('.mm-visor-video');
  const barras = $('.mm-visor-barras');
  const enlaceTienda = $('.mm-visor-tienda');
  const logo = $('.mm-visor-logo');
  const nombre = $('.mm-visor-nombre');
  const etiqueta = $('.mm-visor-etiqueta');
  const titulo = $('.mm-visor-titulo');
  const cargando = $('.mm-visor-cargando');
  const botonProducto = $('.js-visor-producto');
  const botonTienda = $('.js-visor-tienda');
  const botonPausa = $('.js-visor-pausa');
  const botonSonido = $('.js-visor-sonido');
  const zonaAnterior = $('.js-visor-anterior');
  const zonaSiguiente = $('.js-visor-siguiente');

  etiqueta.textContent = datos.dataset.etiqueta || '';
  etiqueta.hidden = !etiqueta.textContent;

  let actual = { grupo: 0, video: 0 };
  let silencio = false;
  let pausado = false;
  let enHistorial = false;
  let origen = null;
  let cuadro = 0;
  const contados = new Set();

  // Vistos en este navegador: el aro de una tienda se apaga cuando ya se vieron todos sus videos.
  const CLAVE = 'mm-videos-vistos';
  const vistos = (() => {
    try { return new Set(JSON.parse(localStorage.getItem(CLAVE) || '[]')); } catch (error) { return new Set(); }
  })();
  const anotarVisto = (id) => {
    vistos.add(id);
    try { localStorage.setItem(CLAVE, JSON.stringify(Array.from(vistos).slice(-200))); } catch (error) { /* sin almacenamiento */ }
  };
  const pintarAros = () => {
    document.querySelectorAll('[data-abrir-historia]').forEach((enlace) => {
      const grupo = grupos[Number(enlace.dataset.abrirHistoria)];
      if (grupo) enlace.classList.toggle('visto', grupo.videos.every((item) => vistos.has(item.id)));
    });
  };

  // Una vista por video y por visita; el servidor ademas la cuenta una sola vez por persona.
  const contarVista = (item) => {
    if (!item.vista || contados.has(item.id)) return;
    contados.add(item.id);
    fetch(item.vista, {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'X-CSRFToken': datos.dataset.csrf || '', 'X-Requested-With': 'fetch' },
    }).catch(() => {});
  };

  const itemActual = () => grupos[actual.grupo].videos[actual.video];

  const pintarPausa = () => {
    botonPausa.setAttribute('aria-label', pausado ? 'Reproducir' : 'Pausar');
    botonPausa.firstElementChild.className = pausado ? 'bi bi-play-fill' : 'bi bi-pause-fill';
  };
  const pintarSonido = () => {
    botonSonido.setAttribute('aria-label', silencio ? 'Activar el sonido' : 'Silenciar');
    botonSonido.firstElementChild.className = silencio ? 'bi bi-volume-mute-fill' : 'bi bi-volume-up-fill';
  };

  function pintarBarras() {
    const cantidad = grupos[actual.grupo].videos.length;
    barras.replaceChildren(...Array.from({ length: cantidad }, (_, indice) => {
      const barra = document.createElement('span');
      const relleno = document.createElement('i');
      relleno.style.transform = `scaleX(${indice < actual.video ? 1 : 0})`;
      barra.appendChild(relleno);
      return barra;
    }));
  }

  function avanzarBarra() {
    const barra = barras.children[actual.video];
    if (barra && video.duration && Number.isFinite(video.duration)) {
      barra.firstElementChild.style.transform = `scaleX(${Math.min(1, video.currentTime / video.duration)})`;
    }
    cuadro = requestAnimationFrame(avanzarBarra);
  }

  function reproducir() {
    const intento = video.play();
    if (!intento || !intento.catch) return;
    intento.catch((error) => {
      // Si el navegador no deja sonar sin otro toque, sigue en silencio y el boton lo dice.
      if (error && error.name === 'NotAllowedError' && !video.muted) {
        silencio = true;
        video.muted = true;
        pintarSonido();
        video.play().catch(() => {});
      }
    });
  }

  function mostrar() {
    const grupo = grupos[actual.grupo];
    const item = itemActual();
    enlaceTienda.href = grupo.url;
    botonTienda.href = grupo.url;
    nombre.textContent = grupo.nombre;
    logo.replaceChildren();
    if (grupo.logo) {
      const imagen = document.createElement('img');
      imagen.src = grupo.logo;
      imagen.alt = '';
      logo.appendChild(imagen);
    } else {
      logo.textContent = grupo.nombre.slice(0, 1).toUpperCase();
    }
    titulo.textContent = item.titulo;
    titulo.hidden = !item.titulo;
    botonProducto.hidden = !item.producto;
    if (item.producto) botonProducto.href = item.producto;
    video.setAttribute('aria-label', item.titulo || `Video de ${grupo.nombre}`);
    pintarBarras();
    pausado = false;
    pintarPausa();
    cargando.hidden = false;
    video.muted = silencio;
    video.src = item.src;
    reproducir();
  }

  function siguiente() {
    if (actual.video < grupos[actual.grupo].videos.length - 1) {
      actual.video += 1;
    } else {
      const proximo = grupos.findIndex((grupo, indice) => indice > actual.grupo && grupo.videos.length);
      if (proximo < 0) { cerrar(); return; }
      actual = { grupo: proximo, video: 0 };
    }
    mostrar();
  }

  function anterior() {
    if (actual.video > 0) {
      actual.video -= 1;
    } else {
      const previo = grupos.map((grupo, indice) => (indice < actual.grupo && grupo.videos.length ? indice : -1))
        .filter((indice) => indice >= 0).pop();
      if (previo === undefined) {
        // Ya es el primero: vuelve a empezar.
        video.currentTime = 0;
        if (!pausado) reproducir();
        return;
      }
      actual = { grupo: previo, video: 0 };
    }
    mostrar();
  }

  function abrir(indice, disparador) {
    if (!grupos[indice] || !grupos[indice].videos.length) return;
    // Si la tienda tiene varios videos se empieza por el primero que no se ha visto.
    const pendiente = grupos[indice].videos.findIndex((item) => !vistos.has(item.id));
    actual = { grupo: indice, video: Math.max(0, pendiente) };
    origen = disparador;
    document.documentElement.classList.add('mm-visor-abierto');
    if (!visor.open) visor.showModal();
    // El boton "atras" del telefono cierra el visor en vez de salir de la pagina.
    if (!enHistorial) {
      history.pushState({ mmVisor: true }, '');
      enHistorial = true;
    }
    cancelAnimationFrame(cuadro);
    cuadro = requestAnimationFrame(avanzarBarra);
    mostrar();
  }

  function cerrar() {
    if (visor.open) visor.close();
  }

  visor.addEventListener('close', () => {
    video.pause();
    video.removeAttribute('src');
    video.load();
    cancelAnimationFrame(cuadro);
    document.documentElement.classList.remove('mm-visor-abierto');
    pintarAros();
    if (enHistorial) {
      enHistorial = false;
      history.back();
    }
    if (origen && typeof origen.focus === 'function') origen.focus();
  });
  window.addEventListener('popstate', () => {
    if (!visor.open) return;
    enHistorial = false;
    visor.close();
  });
  // Al volver con "atras" desde un producto, el navegador puede devolver la pagina con el visor abierto.
  window.addEventListener('pageshow', (evento) => {
    if (evento.persisted && visor.open && !pausado) reproducir();
  });

  video.addEventListener('playing', () => {
    cargando.hidden = true;
    const item = itemActual();
    anotarVisto(item.id);
    contarVista(item);
  });
  video.addEventListener('waiting', () => { cargando.hidden = false; });
  video.addEventListener('canplay', () => { cargando.hidden = true; });
  video.addEventListener('ended', siguiente);
  video.addEventListener('error', () => {
    // Un video que no carga se salta.
    if (visor.open && video.getAttribute('src')) setTimeout(siguiente, 700);
  });

  botonPausa.addEventListener('click', () => {
    pausado = !pausado;
    if (pausado) video.pause(); else reproducir();
    pintarPausa();
  });
  botonSonido.addEventListener('click', () => {
    silencio = !silencio;
    video.muted = silencio;
    pintarSonido();
    if (!silencio && !pausado) reproducir();
  });
  $('.js-visor-cerrar').addEventListener('click', cerrar);
  // En la PC, un clic fuera del video lo cierra.
  visor.addEventListener('click', (evento) => { if (evento.target === visor) cerrar(); });
  visor.addEventListener('keydown', (evento) => {
    if (evento.key === 'ArrowRight') { evento.preventDefault(); siguiente(); }
    if (evento.key === 'ArrowLeft') { evento.preventDefault(); anterior(); }
  });

  // Toque corto: anterior o siguiente. Dedo puesto: pausa mientras no se suelte.
  let espera = 0;
  let sostenido = false;
  [zonaAnterior, zonaSiguiente].forEach((zona) => {
    zona.addEventListener('pointerdown', () => {
      sostenido = false;
      clearTimeout(espera);
      espera = setTimeout(() => { sostenido = true; video.pause(); }, 250);
    });
    const soltar = () => {
      clearTimeout(espera);
      if (sostenido && !pausado && visor.open) reproducir();
    };
    ['pointerup', 'pointercancel', 'pointerleave'].forEach((nombreEvento) => zona.addEventListener(nombreEvento, soltar));
    zona.addEventListener('contextmenu', (evento) => evento.preventDefault());
    zona.addEventListener('click', (evento) => {
      if (sostenido) { sostenido = false; evento.preventDefault(); return; }
      if (zona === zonaAnterior) anterior(); else siguiente();
    });
  });

  document.addEventListener('visibilitychange', () => {
    if (!visor.open) return;
    if (document.hidden) video.pause(); else if (!pausado) reproducir();
  });

  document.addEventListener('click', (evento) => {
    const disparador = evento.target.closest('[data-abrir-historia]');
    if (!disparador) return;
    const indice = Number(disparador.dataset.abrirHistoria);
    if (!grupos[indice]) return;
    evento.preventDefault();
    abrir(indice, disparador);
  });

  pintarAros();
})();
