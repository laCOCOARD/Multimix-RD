/* Comportamiento del panel. Va en un archivo y no dentro de las plantillas: la politica de contenido (CSP) no
   deja correr scripts en linea. */
(() => {
  'use strict';

  // Botones que piden confirmacion antes de enviar (cambiar de estado, liquidar).
  document.addEventListener('click', (evento) => {
    const boton = evento.target.closest('[data-confirmar]');
    if (boton && !window.confirm(boton.dataset.confirmar)) evento.preventDefault();
  });
})();

// Envia las fotos una por una: asi no importa cuantas sean ni cuanto tarde cada una.
(() => {
  const formulario = document.getElementById('fotos-por-sku');
  if (!formulario) return;
  const resumen = document.getElementById('fotos-resumen');
  const tabla = document.getElementById('fotos-rechazadas');
  const boton = formulario.querySelector('[type=submit]');

  const anotarRechazo = (archivo, sku, motivo) => {
    const fila = tabla.tBodies[0].insertRow();
    const celda = document.createElement('th');
    celda.scope = 'row';
    celda.textContent = archivo;
    fila.append(celda);
    fila.insertCell().textContent = sku;
    fila.insertCell().textContent = motivo;
    tabla.hidden = false;
  };

  formulario.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const fotos = Array.from(formulario.elements.fotos.files);
    if (!fotos.length) return;
    const token = formulario.elements.csrfmiddlewaretoken.value;
    let asignadas = 0;
    let rechazadas = 0;

    boton.disabled = true;
    tabla.tBodies[0].replaceChildren();
    tabla.hidden = true;
    document.getElementById('fotos-resultado').hidden = false;

    for (const [indice, foto] of fotos.entries()) {
      resumen.textContent = `Subiendo ${indice + 1} de ${fotos.length}: ${foto.name}`;
      const datos = new FormData();
      datos.append('csrfmiddlewaretoken', token);
      datos.append('fotos', foto);
      if (formulario.elements.tienda) datos.append('tienda', formulario.elements.tienda.value);
      if (formulario.elements.reemplazar.checked) datos.append('reemplazar', '1');
      try {
        const respuesta = await fetch(formulario.action, {
          method: 'POST', body: datos, headers: { 'X-Requested-With': 'fetch' },
        });
        if (!respuesta.ok) throw new Error(`Error ${respuesta.status}`);
        for (const resultado of (await respuesta.json()).resultados) {
          if (resultado.asignada) {
            asignadas += 1;
          } else {
            rechazadas += 1;
            anotarRechazo(resultado.archivo, resultado.sku, resultado.detalle);
          }
        }
      } catch (error) {
        rechazadas += 1;
        anotarRechazo(foto.name, '', `No se pudo subir (${error.message}).`);
      }
    }

    resumen.textContent = `${asignadas} foto(s) asignadas, ${rechazadas} sin asignar.`;
    boton.disabled = false;
    formulario.reset();
  });
})();

// Videos de las tiendas: al elegir el archivo se avisa enseguida si pesa o dura mas de lo permitido, para no esperar a
// que suba. Es solo un aviso: el servidor lo vuelve a revisar al guardar.
(() => {
  document.querySelectorAll('input[type="file"][data-video-segundos]').forEach((campo) => {
    const aviso = document.createElement('p');
    aviso.className = 'panel-aviso-video';
    aviso.setAttribute('role', 'status');
    aviso.hidden = true;
    campo.insertAdjacentElement('afterend', aviso);
    const decir = (texto) => { aviso.textContent = texto; aviso.hidden = !texto; };

    campo.addEventListener('change', () => {
      decir('');
      const archivo = campo.files && campo.files[0];
      if (!archivo) return;
      const segundos = Number(campo.dataset.videoSegundos);
      const megas = Number(campo.dataset.videoMegas);
      if (megas && archivo.size > megas * 1024 * 1024) {
        decir(`Este video pesa ${(archivo.size / 1048576).toFixed(1)} MB y el máximo es ${megas} MB: así no se va a poder guardar.`);
        return;
      }
      const prueba = document.createElement('video');
      const direccion = URL.createObjectURL(archivo);
      prueba.preload = 'metadata';
      prueba.addEventListener('loadedmetadata', () => {
        URL.revokeObjectURL(direccion);
        if (segundos && Number.isFinite(prueba.duration) && prueba.duration > segundos + 0.5) {
          decir(`Este video dura ${Math.round(prueba.duration)} segundos y el máximo es ${segundos}: recórtalo antes de subirlo.`);
        }
      });
      prueba.addEventListener('error', () => URL.revokeObjectURL(direccion));
      prueba.src = direccion;
    });
  });
})();
