// Botones − y + de una cantidad (.js-paso-cantidad con botones [data-paso] y un input numerico).
// Respeta min y max del campo. Con data-enviar en el grupo, el formulario se envia solo al cambiar
// (carrito de todas las tiendas). Sin JavaScript se escribe la cantidad y se usa el boton "Actualizar".
(function () {
  'use strict';

  function ajustar(campo, valor) {
    var minimo = parseInt(campo.min, 10) || 1;
    var maximo = parseInt(campo.max, 10) || Infinity;
    var nuevo = Math.min(Math.max(valor, minimo), maximo);
    if (String(nuevo) !== campo.value) {
      campo.value = nuevo;
      campo.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  document.addEventListener('click', function (evento) {
    var boton = evento.target.closest('.js-paso-cantidad [data-paso]');
    if (!boton) return;
    var campo = boton.closest('.js-paso-cantidad').querySelector('input[type="number"]');
    if (!campo) return;
    ajustar(campo, (parseInt(campo.value, 10) || 0) + parseInt(boton.dataset.paso, 10));
  });

  var esperas = new WeakMap();
  document.addEventListener('change', function (evento) {
    var campo = evento.target;
    var grupo = campo.closest && campo.closest('.js-paso-cantidad[data-enviar]');
    if (!grupo || !campo.form) return;
    clearTimeout(esperas.get(campo.form));
    // Una pausa corta: tocar + tres veces seguidas manda un solo cambio.
    esperas.set(campo.form, setTimeout(function () {
      grupo.classList.add('enviando');
      campo.form.requestSubmit ? campo.form.requestSubmit() : campo.form.submit();
    }, 450));
  });
})();
