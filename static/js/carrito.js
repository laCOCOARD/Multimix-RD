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
    carrito.querySelector('.js-total').textContent = datos.total;
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
          avisar(`Solo hay ${maximo} disponibles.`, 'aviso');
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
