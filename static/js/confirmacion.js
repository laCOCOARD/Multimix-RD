/* Confirmacion: intenta abrir WhatsApp una sola vez justo despues de crear el pedido. */
(() => {
  'use strict';

  const pagina = document.getElementById('confirmacion');
  const boton = document.getElementById('enviar-whatsapp');
  if (!pagina || !boton || pagina.dataset.abrir !== '1') return;

  const clave = `whatsapp-abierto-${pagina.dataset.token}`;
  try {
    if (sessionStorage.getItem(clave)) return;
    sessionStorage.setItem(clave, '1');
  } catch (error) {
    // Sin sessionStorage (modo privado estricto) se intenta igual: el servidor solo lo pide una vez.
  }

  setTimeout(() => {
    const ventana = window.open(boton.href, '_blank', 'noopener');
    // Con "noopener" window.open devuelve null aunque abra; el boton queda resaltado como respaldo.
    if (!ventana) boton.classList.add('mm-llamar');
  }, 900);
})();
