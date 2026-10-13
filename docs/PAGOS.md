# Pagos

Cómo cobra Multimix RD hoy y qué falta para aceptar tarjetas.

## Lo que funciona hoy

Cada pedido tiene un **pago** (`pagos.Pago`) con su propia referencia (`MMX-2026-00012-P1`), su monto y su estado:

| Estado            | Qué significa                                                              |
| ----------------- | -------------------------------------------------------------------------- |
| Pendiente de pago | El pedido existe y todavía no se ha cobrado.                               |
| Pago en revisión  | El cliente avisó que transfirió (con o sin comprobante).                    |
| Pago confirmado   | El vendedor verificó el dinero. El pedido pasa a **Pagado**.               |
| Rechazado         | El comprobante no sirvió. El cliente puede enviar otro (se abre otro pago). |
| Cancelado         | El pedido se canceló antes de cobrarse.                                     |
| Reembolsado       | Reservado para devoluciones; todavía no hay pantalla para registrarlas.     |

- **Transferencia:** el cliente ve las cuentas de la tienda, transfiere y, desde la página de su pedido, adjunta
  la foto o captura del comprobante y la referencia. El vendedor lo revisa en **Panel → Pagos** y lo aprueba o lo
  rechaza. El cliente nunca marca un pedido como pagado.
- **Efectivo (al recoger o contra entrega):** el pago queda pendiente y se confirma solo cuando el vendedor
  marca el pedido como entregado.
- Un pedido no se cobra dos veces: aprobar un pago ya aprobado no hace nada y la base de datos impide dos pagos
  aprobados para el mismo pedido.
- Los comprobantes se guardan como imagen (JPG, PNG o WebP de hasta 5 MB, convertidos a WebP) en la carpeta
  `comprobantes/` del mismo almacenamiento de las fotos. **Ese almacenamiento es público:** el enlace de un
  comprobante es imposible de adivinar, pero quien lo tenga puede abrirlo. Antes de manejar mucho volumen
  conviene pasarlos a un bucket privado.

## Tarjetas: qué falta

La estructura está en `pagos/proveedores.py`, pero **no hay ninguna pasarela conectada** y el sitio no ofrece
pago con tarjeta. Falta, en este orden:

1. **Afiliación del comercio** con AZUL o CardNET a nombre de Multimix RD (una sola para todo el sitio; el
   reparto a cada tienda se hace después). El banco entrega las credenciales de pruebas y de producción.
2. **Documentación y credenciales de pruebas** de la pasarela elegida:
   - AZUL: https://dev.azul.com.do/Pages/developer/pages/lib/index.aspx
   - CardNET: https://developers.cardnet.com.do/guias/boton-de-pago/
3. Con eso se escribe la clase del proveedor (hereda de `ProveedorDePago` y se registra con `registrar`):
   cómo iniciar el cobro, cómo verificar la respuesta y las notificaciones, y cómo reembolsar.
4. Variables de entorno en Render: `PAGOS_PROVEEDOR_TARJETA` con el código del proveedor y las credenciales
   que indique su documentación. Nunca van en el código ni en la base de datos.
5. Pruebas en el entorno de pruebas del proveedor (aprobado, rechazado, cancelado y notificación repetida) antes
   de usar las credenciales reales.
6. Reparto a las tiendas: comisión por tienda, saldo y liquidaciones. Todavía no está construido.

No se guardan números de tarjeta ni códigos de seguridad en ningún caso: del proveedor solo se conservan la
referencia del pago y el código de autorización.
