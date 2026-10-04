/* Checkout: muestra los campos segun la entrega y el pago, valida y pide los totales al servidor. */
(() => {
  'use strict';

  const formulario = document.getElementById('checkout');
  if (!formulario) return;

  const campo = (nombre) => formulario.elements[nombre];
  const bloqueRecoger = formulario.querySelector('.js-bloque-recoger');
  const bloqueEnvio = formulario.querySelector('.js-bloque-envio');
  const bloqueTransferencia = formulario.querySelector('.js-bloque-transferencia');
  const totales = formulario.querySelector('.mm-totales');
  const mensajeCupon = document.getElementById('mensaje-cupon');
  const pagosPorEntrega = {
    recoger: formulario.dataset.pagosRecoger.split(','),
    envio: formulario.dataset.pagosEnvio.split(','),
  };

  const entregaElegida = () => (formulario.querySelector('.js-entrega:checked') || {}).value || 'recoger';
  const pagoElegido = () => (formulario.querySelector('.js-pago:checked') || {}).value || '';

  function ajustarCampos() {
    const entrega = entregaElegida();
    const esEnvio = entrega === 'envio';
    bloqueRecoger.classList.toggle('mm-oculto', esEnvio);
    bloqueEnvio.classList.toggle('mm-oculto', !esEnvio);
    campo('zona').required = esEnvio;
    campo('direccion').required = esEnvio;

    // Solo se ofrecen las formas de pago validas para la entrega elegida.
    const permitidos = pagosPorEntrega[entrega] || [];
    formulario.querySelectorAll('.js-opcion-pago').forEach((opcion) => {
      const permitido = permitidos.includes(opcion.dataset.pago);
      opcion.classList.toggle('mm-oculto', !permitido);
      const radio = opcion.querySelector('input');
      radio.disabled = !permitido;
      if (!permitido) radio.checked = false;
    });
    if (!pagoElegido()) {
      const primero = formulario.querySelector('.js-pago:not(:disabled)');
      if (primero) primero.checked = true;
    }
    bloqueTransferencia.classList.toggle('mm-oculto', pagoElegido() !== 'transferencia');
  }

  async function pedirTotales(conCupon) {
    const datos = new FormData();
    datos.append('csrfmiddlewaretoken', campo('csrfmiddlewaretoken').value);
    datos.append('metodo_entrega', entregaElegida());
    datos.append('zona', campo('zona').value);
    if (conCupon) datos.append('cupon', campo('cupon').value);
    totales.classList.add('mm-cargando');
    try {
      const respuesta = await fetch(formulario.dataset.urlTotales, {
        method: 'POST',
        body: datos,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': campo('csrfmiddlewaretoken').value },
      });
      if (!respuesta.ok) throw new Error('No se pudieron calcular los totales');
      const info = await respuesta.json();
      if (info.vacio) {
        window.location.reload();
        return;
      }
      document.getElementById('total-subtotal').textContent = info.subtotal;
      document.getElementById('total-descuento').textContent = info.descuento;
      document.getElementById('fila-descuento').classList.toggle('d-none', !info.hay_descuento);
      document.getElementById('total-envio').textContent = info.envio;
      document.getElementById('total-total').textContent = info.total;
      if (conCupon || info.cupon_mensaje) {
        mensajeCupon.textContent = info.cupon_mensaje;
        mensajeCupon.className = `small mb-3 ${info.cupon_ok ? 'text-success' : 'text-danger'}`;
        campo('cupon').classList.toggle('is-invalid', !info.cupon_ok);
        campo('cupon').value = info.cupon;
      }
    } catch (error) {
      mensajeCupon.textContent = 'No pudimos actualizar el resumen. El total final se confirma al enviar el pedido.';
      mensajeCupon.className = 'small mb-3 text-danger';
    } finally {
      totales.classList.remove('mm-cargando');
    }
  }

  function validarTelefono() {
    const telefono = campo('telefono');
    let digitos = telefono.value.replace(/\D/g, '');
    if (digitos.length === 11 && digitos.startsWith('1')) digitos = digitos.slice(1);
    const valido = /^(809|829|849)\d{7}$/.test(digitos);
    telefono.setCustomValidity(valido ? '' : 'Teléfono inválido');
    return valido;
  }

  formulario.querySelectorAll('.js-entrega').forEach((radio) => radio.addEventListener('change', () => {
    ajustarCampos();
    pedirTotales(false);
  }));
  formulario.querySelectorAll('.js-pago').forEach((radio) => radio.addEventListener('change', ajustarCampos));
  campo('zona').addEventListener('change', () => pedirTotales(false));
  campo('telefono').addEventListener('input', validarTelefono);
  document.getElementById('aplicar-cupon').addEventListener('click', () => pedirTotales(true));
  campo('cupon').addEventListener('keydown', (evento) => {
    if (evento.key === 'Enter') {
      evento.preventDefault();
      pedirTotales(true);
    }
  });

  formulario.addEventListener('submit', (evento) => {
    validarTelefono();
    if (!formulario.checkValidity()) {
      evento.preventDefault();
      formulario.classList.add('was-validated');
      const primero = formulario.querySelector(':invalid');
      if (primero) primero.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    const boton = document.getElementById('confirmar');
    boton.disabled = true;
    boton.textContent = 'Enviando pedido…';
  });

  // Si el navegador restaura la pagina desde su cache (boton Atras), se reactiva el boton.
  window.addEventListener('pageshow', () => {
    const boton = document.getElementById('confirmar');
    boton.disabled = false;
    boton.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Confirmar pedido';
  });

  ajustarCampos();
})();
