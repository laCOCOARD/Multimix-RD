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

  // Aparicion suave de los elementos al entrar en pantalla.
  const elementos = document.querySelectorAll('.revelar');
  if ('IntersectionObserver' in window) {
    const observador = new IntersectionObserver((entradas) => {
      entradas.forEach((entrada) => {
        if (entrada.isIntersecting) {
          entrada.target.classList.add('visible');
          observador.unobserve(entrada.target);
        }
      });
    }, { rootMargin: '0px 0px -40px 0px', threshold: 0.05 });
    elementos.forEach((elemento) => observador.observe(elemento));
  } else {
    elementos.forEach((elemento) => elemento.classList.add('visible'));
  }

  // Agregar al carrito sin recargar. Si algo falla, el formulario se envia de la forma normal.
  document.addEventListener('submit', async (evento) => {
    const formulario = evento.target.closest('form.js-agregar');
    if (!formulario) return;
    if (!formulario.checkValidity()) return;
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
})();
