/* Videos de las tiendas dentro de la pagina (includes/video_anuncio.html).
 *
 * Cada video se reproduce solo y sin sonido cuando al menos la mitad se ve en la pantalla, y se pausa al salir.
 * Suena uno a la vez. Tocar el video lo pausa o lo sigue; el boton del altavoz le pone sonido. "Omitir anuncio"
 * lo quita y no vuelve a salir mientras dure la visita (sessionStorage). El video solo se descarga al verse. */
(() => {
  'use strict';

  const bloques = Array.from(document.querySelectorAll('.js-video-anuncio'));
  if (!bloques.length) return;

  const CLAVE = 'mm-videos-omitidos';
  const omitidos = (() => {
    try { return new Set(JSON.parse(sessionStorage.getItem(CLAVE) || '[]')); } catch (error) { return new Set(); }
  })();
  const guardarOmitidos = () => {
    try { sessionStorage.setItem(CLAVE, JSON.stringify(Array.from(omitidos).slice(-100))); } catch (error) { /* sin almacenamiento */ }
  };

  const contados = new Set();
  // Una vista por video y por pagina; el servidor ademas la cuenta una sola vez por persona.
  const contarVista = (bloque) => {
    const id = bloque.dataset.id;
    if (!bloque.dataset.vista || contados.has(id)) return;
    contados.add(id);
    fetch(bloque.dataset.vista, {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'X-CSRFToken': bloque.dataset.csrf || '', 'X-Requested-With': 'fetch' },
    }).catch(() => {});
  };

  const reproducir = (video) => {
    const intento = video.play();
    if (intento && intento.catch) intento.catch(() => {});
  };

  const videos = [];
  const pausarLosDemas = (actual) => {
    videos.forEach((video) => { if (video !== actual && !video.paused) video.pause(); });
  };

  const observador = 'IntersectionObserver' in window
    ? new IntersectionObserver((entradas) => {
      entradas.forEach((entrada) => {
        const video = entrada.target.querySelector('video');
        if (!video) return;
        const visible = entrada.isIntersecting && entrada.intersectionRatio >= 0.5;
        entrada.target.dataset.visible = visible ? '1' : '';
        if (visible && !document.hidden && !entrada.target.dataset.pausado) reproducir(video);
        else if (!visible && !video.paused) video.pause();
      });
    }, { threshold: [0, 0.5] })
    : null;

  const pintarSonido = (boton, video) => {
    boton.setAttribute('aria-label', video.muted ? 'Activar el sonido' : 'Silenciar');
    boton.firstElementChild.className = video.muted ? 'bi bi-volume-mute-fill' : 'bi bi-volume-up-fill';
  };

  bloques.forEach((bloque) => {
    if (omitidos.has(bloque.dataset.id)) { bloque.remove(); return; }
    const video = bloque.querySelector('video');
    const sonido = bloque.querySelector('.js-video-sonido');
    const omitir = bloque.querySelector('.js-video-omitir');
    if (!video) return;
    videos.push(video);

    video.addEventListener('playing', () => { pausarLosDemas(video); contarVista(bloque); });

    // Sin IntersectionObserver (navegadores muy viejos) se quedan los controles del navegador.
    if (observador) {
      video.controls = false;
      video.muted = true;
      if (sonido) {
        sonido.hidden = false;
        pintarSonido(sonido, video);
        sonido.addEventListener('click', () => {
          video.muted = !video.muted;
          pintarSonido(sonido, video);
          if (!video.muted) { delete bloque.dataset.pausado; reproducir(video); }
        });
      }
      video.addEventListener('click', () => {
        if (video.paused) { delete bloque.dataset.pausado; reproducir(video); } else { bloque.dataset.pausado = '1'; video.pause(); }
      });
      observador.observe(bloque);
    }

    if (omitir) {
      omitir.addEventListener('click', () => {
        video.pause();
        video.removeAttribute('src');
        video.load();
        omitidos.add(bloque.dataset.id);
        guardarOmitidos();
        if (observador) observador.unobserve(bloque);
        bloque.classList.add('omitido');
        setTimeout(() => bloque.remove(), 250);
      });
    }
  });

  document.addEventListener('visibilitychange', () => {
    videos.forEach((video) => {
      const bloque = video.closest('.js-video-anuncio');
      if (document.hidden) video.pause();
      else if (bloque && bloque.dataset.visible && !bloque.dataset.pausado) reproducir(video);
    });
  });
})();
