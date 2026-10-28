/* Carrito: cambiar cantidades y eliminar sin recargar. Sin JavaScript los formularios funcionan igual. */
(() => {
  'use strict';

  const carrito = document.getElementById('carrito');
  if (!carrito || !window.Multimix) return;
  const { enviar, avisar, actualizarContador } = window.Multimix;

  function pintar(datos) {
    actualizarContador(datos.cantidad_total);
    if (datos.vacio || datos.aviso_cupon) {
      // Carrito vacio o cupon retirado: se recarga para mostrar el estado completo.
      window.location.reload();
      return;
    }
    carrito.querySelectorAll('.js-linea').forEach((fila) => {
      const linea = datos.lineas[fila.dataset.producto];
      if (!linea) {
        fila.remove();
        return;
      }
      fila.querySelector('.js-cantidad').value = linea.cantidad;
      fila.querySelector('.js-subtotal-linea').textContent = linea.subtotal;
    });
    carrito.querySelector('.js-subtotal').textContent = datos.subtotal;
    carrito.querySelector('.js-descuento').textContent = datos.descuento;
    carrito.querySelector('.js-fila-descuento').classList.toggle('d-none', !datos.hay_descuento);
    carrito.querySelector('.js-impuesto').textContent = datos.impuesto;
    carrito.querySelector('.js-fila-impuesto').classList.toggle('d-none', !datos.hay_impuesto);
    carrito.querySelector('.js-total').textContent = datos.total;
    pintarEnvioGratis(datos.envio_gratis);
  }

  // La barra de envio gratis se arma con nodos: el texto viene del servidor, pero nunca como HTML.
  function pintarEnvioGratis(progreso) {
    const caja = carrito.querySelector('.js-envio-gratis');
    if (!caja || !progreso) return;
    caja.classList.toggle('logrado', progreso.logrado);
    caja.querySelector('.js-envio-gratis-barra').style.width = `${progreso.porcentaje}%`;
    caja.querySelector('[role="progressbar"]').setAttribute('aria-valuenow', progreso.porcentaje);
    const texto = caja.querySelector('.js-envio-gratis-texto');
    texto.replaceChildren();
    if (progreso.logrado) {
      const icono = document.createElement('i');
      icono.className = 'bi bi-truck me-1';
      texto.append(icono, '¡Tu envío a domicilio es gratis!');
    } else {
      const monto = document.createElement('strong');
      monto.textContent = progreso.falta;
      texto.append('Te faltan ', monto, ' para el envío gratis.');
    }
  }

  async function mandar(fila, formulario) {
    fila.classList.add('mm-ocupada');
    try {
      const datos = await enviar(formulario.action, new FormData(formulario));
      if (datos.mensaje) avisar(datos.mensaje, datos.ok ? 'aviso' : 'error');
      pintar(datos);
    } catch (error) {
      formulario.submit();
      return;
    }
    fila.classList.remove('mm-ocupada');
  }

  carrito.querySelectorAll('.js-linea').forEach((fila) => {
    const formulario = fila.querySelector('.js-form-cantidad');
    const campo = fila.querySelector('.js-cantidad');
    let espera;

    const programar = () => {
      clearTimeout(espera);
      espera = setTimeout(() => {
        const maximo = parseInt(campo.max, 10) || 1;
        let cantidad = parseInt(campo.value, 10);
        if (Number.isNaN(cantidad) || cantidad < 1) cantidad = 1;
        if (cantidad > maximo) {
          cantidad = maximo;
          avisar(`Puedes llevar hasta ${maximo} por pedido.`, 'aviso');
        }
        campo.value = cantidad;
        mandar(fila, formulario);
      }, 350);
    };

    campo.addEventListener('change', programar);
    fila.querySelector('.js-menos').addEventListener('click', () => {
      campo.value = Math.max((parseInt(campo.value, 10) || 1) - 1, 1);
      programar();
    });
    fila.querySelector('.js-mas').addEventListener('click', () => {
      campo.value = (parseInt(campo.value, 10) || 0) + 1;
      programar();
    });
    formulario.addEventListener('submit', (evento) => {
      evento.preventDefault();
      programar();
    });

    fila.querySelector('.js-form-eliminar').addEventListener('submit', (evento) => {
      evento.preventDefault();
      mandar(fila, evento.target);
    });
  });
})();
