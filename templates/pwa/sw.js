{% load static %}/* Service worker de la app instalable. Lo sirve core.views.service_worker desde la raiz del sitio.

   - Paginas: siempre de la red (precios, carrito y pedidos tienen que estar al dia); sin conexion, la pagina
     "Sin conexion". Nunca se guardan paginas: pueden traer datos de la cuenta.
   - Estaticos (/static/): de la cache si estan, y si no, de la red y se guardan. Sus nombres cambian con cada
     version, asi que nunca quedan viejos.
   - Formularios (POST) y otros sitios: no los toca. */
'use strict';

const CACHE = 'multimix-{{ version }}';
const SIN_CONEXION = '{% url "core:sin_conexion" %}';
const ESTATICOS = '{% get_static_prefix %}';
const PRECARGA = [
  SIN_CONEXION,
  '{% static "css/tienda.css" %}',
  '{% static "js/tienda.js" %}',
  '{% static "js/js-activo.js" %}',
  '{% static "img/logo-simbolo.webp" %}',
  '{% static "img/icono-192.png" %}',
  '{% static "fonts/inter-latin-wght-normal.woff2" %}',
];

self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECARGA)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(
        nombres.filter((nombre) => nombre.startsWith('multimix-') && nombre !== CACHE).map((nombre) => caches.delete(nombre)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (evento) => {
  const peticion = evento.request;
  if (peticion.method !== 'GET') return;
  const url = new URL(peticion.url);
  if (url.origin !== self.location.origin) return;

  if (peticion.mode === 'navigate') {
    evento.respondWith(fetch(peticion).catch(() => caches.match(SIN_CONEXION)));
    return;
  }
  if (url.pathname.startsWith(ESTATICOS)) {
    evento.respondWith(
      caches.match(peticion).then((guardada) => guardada || fetch(peticion).then((respuesta) => {
        if (respuesta.ok) {
          const copia = respuesta.clone();
          caches.open(CACHE).then((cache) => cache.put(peticion, copia));
        }
        return respuesta;
      })),
    );
  }
});
