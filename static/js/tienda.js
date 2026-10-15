/* Comportamiento comun de la tienda: animaciones, avisos y "agregar al carrito" sin recargar. */
(() => {
  'use strict';

  const escapar = (texto) => {
    const nodo = document.createElement('div');
    nodo.textContent = texto;
    return nodo.innerHTML;
  };

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

  function avisar(mensaje, tipo = 'exito') {
    const contenedor = document.getElementById('avisos');
    if (!mensaje || !contenedor || !window.bootstrap) return;
    const colores = { exito: 'text-bg-success', error: 'text-bg-danger', aviso: 'text-bg-warning' };
    const toast = document.createElement('div');
    toast.className = `toast align-items-center border-0 ${colores[tipo] || colores.exito}`;
    toast.setAttribute('role', 'status');
    toast.innerHTML = `<div class="d-flex"><div class="toast-body">${escapar(mensaje)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button></div>`;
    contenedor.appendChild(toast);
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    new bootstrap.Toast(toast, { delay: 3500 }).show();
  }

  function actualizarContador(cantidad) {
    document.querySelectorAll('.js-contador-carrito').forEach((contador) => {
      contador.textContent = cantidad;
      contador.classList.toggle('d-none', !cantidad);
      contador.classList.remove('mm-salto');
      void contador.offsetWidth;
      contador.classList.add('mm-salto');
    });
  }

  window.Multimix = { enviar, avisar, actualizarContador };

  // Aparicion al deslizar. Cada grupo entra con su estilo y, si entran varios a la vez, en cascada.
  const quieto = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const animar = (selector, ...clases) => document.querySelectorAll(selector).forEach((nodo) => nodo.classList.add('revelar', ...clases));
  animar('.mm-seccion-cabecera, .mm-legal-cabecera, main h1:not(.mm-portada-titulo):not(.mm-banner-titulo)', 'revelar-izq');
  animar('.mm-burbuja', 'revelar-zoom');
  animar('.mm-tienda-tarjeta, .mm-llamado, .mm-filtros, .mm-panel, .mm-legal-indice');
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

  // Al deslizar: barra de progreso, cabecera con sombra, boton para volver arriba y fondo de la portada mas lento.
  const progreso = document.querySelector('.mm-progreso');
  const cabecera = document.querySelector('.mm-cabecera');
  const arriba = document.querySelector('.mm-arriba');
  const capas = quieto ? [] : Array.from(document.querySelectorAll('.mm-portada > .container, .mm-banner .container'));
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
    const boton = formulario.querySelector('[type="submit"]');
    boton.disabled = true;
    try {
      const datos = await enviar(formulario.action, new FormData(formulario));
      actualizarContador(datos.cantidad_total);
      avisar(datos.mensaje, datos.ok ? 'exito' : 'error');
    } catch (error) {
      formulario.classList.remove('js-agregar');
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

    function pintar(resultados, texto) {
      lista.replaceChildren();
      resultados.forEach((resultado, i) => {
        const enlace = document.createElement('a');
        enlace.href = resultado.url;
        enlace.id = `${lista.id}-${i}`;
        enlace.setAttribute('role', 'option');
        if (resultado.foto) {
          const foto = document.createElement('img');
          foto.src = resultado.foto;
          foto.alt = '';
          foto.width = 44;
          foto.height = 44;
          enlace.appendChild(foto);
        }
        const cuerpo = document.createElement('span');
        cuerpo.className = 'mm-sugerencia-cuerpo';
        const nombre = document.createElement('span');
        nombre.className = 'mm-sugerencia-nombre';
        nombre.textContent = resultado.nombre;
        const detalle = document.createElement('span');
        detalle.className = 'mm-sugerencia-detalle';
        detalle.textContent = resultado.tienda ? `${resultado.precio} · ${resultado.tienda}` : resultado.precio;
        cuerpo.append(nombre, detalle);
        enlace.appendChild(cuerpo);
        const fila = document.createElement('li');
        fila.setAttribute('role', 'none');
        fila.appendChild(enlace);
        lista.appendChild(fila);
      });
      if (resultados.length) {
        const fila = document.createElement('li');
        fila.setAttribute('role', 'none');
        const todos = document.createElement('a');
        todos.href = `${formulario.action}?q=${encodeURIComponent(texto)}`;
        todos.id = `${lista.id}-todos`;
        todos.className = 'mm-sugerencia-todos';
        todos.setAttribute('role', 'option');
        todos.textContent = `Ver todos los resultados de «${texto}»`;
        fila.appendChild(todos);
        lista.appendChild(fila);
      }
      activa = -1;
      lista.hidden = !resultados.length;
      campo.setAttribute('aria-expanded', String(!!resultados.length));
    }

    async function buscar() {
      const texto = campo.value.trim();
      if (texto.length < 2) { cerrar(); return; }
      const turno = ++pedido;
      try {
        const respuesta = await fetch(`${origen}?q=${encodeURIComponent(texto)}`, { credentials: 'same-origin' });
        if (!respuesta.ok) throw new Error('sin sugerencias');
        const datos = await respuesta.json();
        // Solo se pinta la respuesta de lo ultimo que se escribio.
        if (turno === pedido) pintar(datos.resultados || [], texto);
      } catch (error) {
        cerrar();
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

  // Galeria del producto: cambiar la foto grande al tocar una miniatura.
  const fotoPrincipal = document.getElementById('foto-principal');
  if (fotoPrincipal) {
    document.querySelectorAll('.js-miniatura').forEach((miniatura) => {
      miniatura.addEventListener('click', (evento) => {
        evento.preventDefault();
        fotoPrincipal.src = miniatura.href;
        document.querySelectorAll('.js-miniatura').forEach((otra) => otra.classList.remove('activa'));
        miniatura.classList.add('activa');
      });
    });
  }

  // Filas que se deslizan: flechas en pantallas con raton y, con data-auto, avance solo cada pocos segundos.
  const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
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
})();
