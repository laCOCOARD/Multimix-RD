# Pagos

Cómo cobra Multimix RD hoy y qué falta para aceptar tarjetas.

## Lo que funciona hoy

Cada pedido tiene un **pago** (`pagos.Pago`) con su propia referencia (`MMX-2026-00012-P1`), su monto y su estado:

| Estado            | Qué significa                                                              |
| ----------------- | -------------------------------------------------------------------------- |
| Pendiente de pago | El pedido existe y todavía no se ha cobrado.                               |
| Pago en revisión  | El cliente subió el comprobante de su transferencia.                        |
| Pago confirmado   | El vendedor verificó el dinero. El pedido pasa a **Pagado**.               |
| Rechazado         | El comprobante no sirvió. El cliente puede enviar otro (se abre otro pago). |
| Cancelado         | El pedido se canceló antes de cobrarse.                                     |
| Reembolsado       | Reservado para devoluciones; todavía no hay pantalla para registrarlas.     |

- **Transferencia:** el cliente ve las cuentas del sitio (las del dueño, iguales en todas las tiendas), transfiere y
  sube la foto o captura del comprobante (en el checkout o después, en la página de su pedido), con la referencia
  si quiere. **El comprobante es obligatorio:** sin él no hay aviso de transferencia. El administrador lo revisa en
  **Panel → Pagos** y lo aprueba o lo rechaza. El cliente nunca marca un pedido como pagado.
- **Efectivo (al recoger o contra entrega):** el pago queda pendiente y se confirma solo cuando el vendedor
  marca el pedido como entregado.
- Un pedido no se cobra dos veces: aprobar un pago ya aprobado no hace nada y la base de datos impide dos pagos
  aprobados para el mismo pedido.
- Los comprobantes se guardan como imagen (JPG, PNG o WebP de hasta 5 MB, convertidos a WebP) en el bucket
  **privado** `multimix-privado`: no tienen dirección pública y solo se ven desde el panel, a quien le toca ese pago.

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
6. Con tarjeta, el dinero entra al sitio: el pedido debe nacer con `cobra_el_sitio=True` (en `crear_pedido`) para
   que entre al reparto de abajo como cobrado por el sitio.

No se guardan números de tarjeta ni códigos de seguridad en ningún caso: del proveedor solo se conservan la
referencia del pago y el código de autorización.

## Reparto a las tiendas

**Panel → Liquidaciones → Saldos por tienda** (solo el administrador principal).

- Cada tienda tiene su propia **comisión del sitio (%)**.
  Se cambian en **Tiendas → la tienda → Reparto**. El vendedor no las ve.
- Entra en cuenta un pedido **cobrado y ya entregado**. Lo cobrado sin entregar aparece como "en curso".
- La comisión se calcula sobre los productos (subtotal menos descuento). El envío es completo de la tienda.
- Las transferencias las recibe el sitio y se le depositan a la tienda menos la comisión. El efectivo lo cobra la
  tienda al entregar: va en su propio apartado ("Lo cobró la tienda"), no se le deposita, y la comisión de esas
  ventas se descuenta del depósito. Un saldo negativo significa que la tienda le debe al sitio. Cada saldo trae
  la lista de sus pedidos con la forma de pago y quién cobró.

### Las transferencias las recibe el sitio

1. El cliente de cualquier tienda ve las **cuentas bancarias del sitio** (Panel → Cuentas bancarias del sitio, solo
   el administrador principal). Las tiendas no registran cuentas. Queda anotado en el pedido (`cobra_el_sitio`).
2. El aviso de transferencia y el comprobante le llegan al correo del sitio (Configuración general; si no tiene,
   a los administradores principales).
3. El administrador comprueba en la app del banco que el dinero llegó y aprueba o rechaza en **Pagos**. El
   vendedor ve el pago y el aviso "El sitio verifica el pago", pero no puede aprobarlo, rechazarlo, marcar el
   pedido como pagado o reembolsado, ni cancelarlo si el cliente ya dijo que transfirió.
4. Al aprobar, la tienda recibe el correo **"Pago confirmado"** con los productos y la entrega, y sigue con el
   pedido (preparando, enviado, entregado) como siempre.
- Al registrar el depósito se puede anotar la **comisión del banco por la transferencia**: la paga el sitio. Queda
  guardada en la liquidación como gasto del sitio, pero **no** se le descuenta a la tienda, que recibe su saldo
  completo. El vendedor no ve ese dato.
- **Registrar liquidación** guarda el depósito (con su referencia) y marca los pedidos para no pagarlos dos veces.
  Cambiar la comisión después no altera lo ya liquidado. Un pedido liquidado que luego se reembolsa se descuenta
  en la siguiente liquidación.
- Cada tienda ve sus liquidaciones en su panel, y en la lista de pedidos puede filtrar los ya liquidados.
