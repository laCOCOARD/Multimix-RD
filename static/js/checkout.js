/* Checkout: lo recorre paso a paso, muestra los campos segun la entrega y el pago y pide los totales al servidor. */
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
  const botonConfirmar = document.getElementById('confirmar');
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
    campo('sector').required = esEnvio;
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
      document.getElementById('total-impuesto').textContent = info.impuesto;
      document.getElementById('fila-impuesto').classList.toggle('d-none', !info.hay_impuesto);
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

  // --- Pasos ---------------------------------------------------------------------------
  const pasos = Array.from(formulario.querySelectorAll('[data-paso]'));
  const indicadores = Array.from(document.querySelectorAll('#pasos-checkout [data-ir]'));
  let actual = 0;

  const camposDe = (paso) => Array.from(paso.querySelectorAll('input, select, textarea')).filter((c) => !c.disabled);
  const pasoDe = (elemento) => pasos.indexOf(elemento.closest('[data-paso]'));

  function pasoValido(indice) {
    validarTelefono();
    const paso = pasos[indice];
    const invalido = camposDe(paso).find((c) => !c.checkValidity());
    paso.classList.toggle('was-validated', !!invalido);
    if (invalido) invalido.focus();
    return !invalido;
  }

  function texto(nodo, lineas) {
    nodo.replaceChildren();
    lineas.filter(Boolean).forEach((linea, i) => {
      if (i) nodo.appendChild(document.createElement('br'));
      nodo.appendChild(document.createTextNode(linea));
    });
  }

  function pintarRevision() {
    const revision = document.getElementById('revision');
    if (!revision) return;
    const etiqueta = (radio) => {
      const nodo = radio && formulario.querySelector(`label[for="${radio.id}"] span`);
      return nodo ? nodo.firstChild.textContent.trim() : '';
    };
    texto(revision.querySelector('[data-revision="cliente"]'), [
      campo('nombre').value.trim(), campo('telefono').value.trim(), campo('correo').value.trim(),
    ]);
    const entrega = formulario.querySelector('.js-entrega:checked');
    const lineasEntrega = [etiqueta(entrega)];
    if (entregaElegida() === 'envio') {
      const zona = campo('zona').selectedOptions[0];
      lineasEntrega.push(
        [campo('direccion').value.trim(), campo('sector').value.trim()].filter(Boolean).join(', '),
        zona && zona.value ? zona.dataset.nombre : '',
        campo('referencia').value.trim(),
      );
    }
    texto(revision.querySelector('[data-revision="entrega"]'), lineasEntrega);
    texto(revision.querySelector('[data-revision="pago"]'), [etiqueta(formulario.querySelector('.js-pago:checked'))]);
  }

  function mostrar(indice, enfocar) {
    actual = Math.max(0, Math.min(indice, pasos.length - 1));
    pasos.forEach((paso, i) => paso.classList.toggle('mm-oculto', i !== actual));
    indicadores.forEach((indicador, i) => {
      indicador.classList.toggle('activo', i === actual);
      indicador.classList.toggle('hecho', i < actual);
      if (i === actual) indicador.setAttribute('aria-current', 'step');
      else indicador.removeAttribute('aria-current');
    });
    if (actual === pasos.length - 1) pintarRevision();
    if (enfocar) {
      const titulo = pasos[actual].querySelector('h2');
      if (titulo) titulo.focus({ preventScroll: true });
      document.getElementById('pasos-checkout').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /** Avanza hasta `destino` mientras los pasos anteriores esten completos. */
  function irA(destino) {
    if (destino <= actual) { mostrar(destino, true); return; }
    for (let i = actual; i < destino; i += 1) {
      if (!pasoValido(i)) { mostrar(i, false); return; }
    }
    mostrar(destino, true);
  }

  formulario.querySelectorAll('.js-siguiente').forEach((boton) => boton.addEventListener('click', () => irA(actual + 1)));
  formulario.querySelectorAll('.js-anterior').forEach((boton) => boton.addEventListener('click', () => irA(actual - 1)));
  indicadores.forEach((indicador, i) => {
    indicador.tabIndex = 0;
    indicador.setAttribute('role', 'button');
    indicador.addEventListener('click', () => irA(i));
    indicador.addEventListener('keydown', (evento) => {
      if (evento.key === 'Enter' || evento.key === ' ') { evento.preventDefault(); irA(i); }
    });
  });
  // Enter en un campo de texto avanza de paso en vez de enviar el pedido a medias.
  formulario.addEventListener('keydown', (evento) => {
    if (evento.key !== 'Enter' || actual === pasos.length - 1) return;
    if (evento.target.matches('input:not([type="checkbox"]):not([type="radio"]), select') && evento.target.name !== 'cupon') {
      evento.preventDefault();
      irA(actual + 1);
    }
  });

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
    for (let i = 0; i < pasos.length; i += 1) {
      if (!pasoValido(i)) {
        evento.preventDefault();
        mostrar(i, false);
        return;
      }
    }
    botonConfirmar.disabled = true;
    botonConfirmar.textContent = 'Creando tu pedido…';
  });

  // Si el navegador restaura la pagina desde su cache (boton Atras), se reactiva el boton.
  window.addEventListener('pageshow', () => {
    botonConfirmar.disabled = false;
    botonConfirmar.replaceChildren();
    const icono = document.createElement('i');
    icono.className = 'bi bi-check2-circle me-1';
    botonConfirmar.append(icono, 'Confirmar pedido');
  });

  ajustarCampos();
  // Si el servidor devolvio errores, se abre el paso que tiene el primero; si no, se empieza por el principio.
  const conError = formulario.querySelector('[data-paso] .is-invalid, [data-paso] .text-danger');
  if (conError) mostrar(pasoDe(conError), false);
  else mostrar(formulario.dataset.enviado ? pasos.length - 1 : 0, false);
})();
