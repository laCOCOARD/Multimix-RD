# Pagos

Cómo se cobra en Multimix RD: lo que pagan los clientes a cada tienda y lo que pagan las tiendas al sitio.

Desde el **26 de octubre de 2026** (pedido del dueño) **cada tienda cobra lo suyo**: sus clientes le transfieren a
sus propias cuentas y ella confirma el pago. El sitio ya no recibe el dinero de las ventas ni se queda con un
porcentaje de cada una: lo que cobra a las tiendas es su **plan** (ver abajo).

## Lo que pagan los clientes

Cada pedido tiene un **pago** (`pagos.Pago`) con su propia referencia (`MMX-2026-00012-P1`), su monto y su estado:

| Estado            | Qué significa                                                              |
| ----------------- | -------------------------------------------------------------------------- |
| Pendiente de pago | El pedido existe y todavía no se ha cobrado.                               |
| Pago en revisión  | El cliente subió el comprobante de su transferencia.                        |
| Pago confirmado   | La tienda verificó el dinero. El pedido pasa a **Pagado**.                 |
| Rechazado         | El comprobante no sirvió. El cliente puede enviar otro (se abre otro pago). |
| Cancelado         | El pedido se canceló antes de cobrarse.                                     |
| Reembolsado       | El pedido se reembolsó.                                                     |

- **Transferencia:** el cliente ve las **cuentas de la tienda** (Panel → Tiendas → Cuentas bancarias de la tienda,
  las registra el vendedor), transfiere y sube la foto o captura del comprobante (en el checkout o después, en la
  página de su pedido). **El comprobante es obligatorio.** El aviso le llega a la tienda, que lo revisa en
  **Panel → Pagos** y lo aprueba o lo rechaza. El cliente nunca marca un pedido como pagado.
- **Una tienda sin cuentas activas no ofrece transferencia**: solo efectivo al recoger o contra entrega (si lo
  permite). Si tampoco acepta contra entrega, el envío a domicilio queda sin forma de pago y el checkout lo avisa.
- **Efectivo (al recoger o contra entrega):** el pago queda pendiente y se confirma cuando la tienda marca el pedido
  como entregado.
- Un pedido no se cobra dos veces: aprobar un pago ya aprobado no hace nada y la base de datos impide dos pagos
  aprobados para el mismo pedido.
- Los comprobantes se guardan como imagen (convertidos a WebP) en el bucket **privado** `multimix-privado`: no
  tienen dirección pública y solo se ven desde el panel, a quien le toca ese pago.

### Los pedidos de antes del 26 de octubre

Del 15 al 26 de octubre de 2026 los clientes de todas las tiendas transferían a las cuentas del sitio. Esos pedidos
llevan `cobra_el_sitio` y siguen como entonces: el comprobante le llega al sitio, solo el administrador principal
aprueba, rechaza, marca pagado o reembolsa, y al aprobar la tienda recibe "Pago confirmado". El dinero de esos
pedidos se le deposita a cada tienda con el **reparto** (Panel → Liquidaciones → Saldos por tienda), menos la
comisión que tenía la tienda (`Tienda.comision_porcentaje`). Lo que cobra la tienda ya no paga comisión.

## Lo que pagan las tiendas al sitio: planes

**Panel → Planes y pagos al sitio.** Hay tres planes (Básico, Estándar y Premium); el administrador cambia sus
montos y límites en **Planes** y asigna el de cada tienda en **Tiendas → la tienda → Plan y cobros**. A una tienda
sin plan no se le cobra nada y no puede anunciarse.

Cada plan define:

- **Mensualidad.** Vence el **día 1** de cada mes. El cargo aparece una semana antes. Quien recibe un plan a mitad
  de mes empieza a pagar el mes siguiente.
- **Pedidos incluidos al mes** y **porcentaje por los pedidos de más.** El día 1 se cuentan los pedidos cobrados del
  mes anterior (con fecha de pago y que no se cancelaron ni reembolsaron); los que pasan del límite son los últimos
  cobrados, y se cobra el porcentaje de lo vendido en ellos (productos menos descuento, sin el envío). Ese cargo
  vence también el día 1.
- **Anuncios en la portada** (banners que la tienda crea en Panel → Anuncios en la portada y que salen cuando el
  administrador los aprueba; cambiar el texto, la imagen o el producto pide aprobarlo otra vez) y **productos
  anunciados** (la casilla "Anunciar en la portada" del producto: salen primero en "Descubre productos" con la
  etiqueta "Patrocinado"). La portada siempre dice que son anuncios.

### Cómo pagan y qué pasa si no pagan

1. La tienda ve en su panel lo que debe, cuándo vence y a qué cuentas transferir (las **cuentas del sitio**, Panel →
   Cuentas bancarias del sitio, que registra solo el administrador).
2. Transfiere y sube el comprobante en **Mensualidades y cargos**. El administrador recibe un correo, lo revisa y lo
   confirma ("Confirmar pago") o lo rechaza; la tienda recibe la respuesta por correo. El administrador también
   puede confirmar un pago que recibió de otra forma, anular un cargo o crear uno a mano.
3. Recordatorios por correo a los vendedores y al correo de la tienda: 3 días antes de vencer (se cambia en
   Configuración general), el día que vence y el último día de gracia.
4. Con un cargo vencido y sin comprobante, pasados los **4 días de gracia** (Configuración general) la tienda se
   **cierra**: deja de verse en el sitio, pero el vendedor sigue entrando al panel para pagar y atender sus pedidos.
   Le llega un correo a la tienda y otro al administrador.
5. Queda cerrada **hasta que el administrador la habilita** (encender "Activa" en la tienda o la acción "Habilitar").
   Lo que ya estaba vencido al habilitarla no la vuelve a cerrar; los cargos siguientes sí cuentan.

Todo esto corre solo en las tareas periódicas (como mucho una vez por hora, con cualquier visita). Donde haya cron se
puede usar `python manage.py revisar_cobros` una vez al día.

## Tarjetas: qué falta

La estructura está en `pagos/proveedores.py`, pero **no hay ninguna pasarela conectada** y el sitio no ofrece
pago con tarjeta.

**Decisión del dueño (2026-10-26):** una **sola afiliación, la del dueño**, para que el cliente pueda tener **un solo
carrito con productos de todas las tiendas** y pagarlo de una vez; después el dueño **le reparte a cada tienda** lo
suyo. Es el siguiente paso: hoy el carrito es de una sola tienda. Hace falta:

1. **Afiliación del comercio** con AZUL o CardNET a nombre del dueño. El banco entrega las credenciales de pruebas y
   de producción.
2. **Documentación y credenciales de pruebas** de la pasarela elegida:
   - AZUL: https://dev.azul.com.do/Pages/developer/pages/lib/index.aspx
   - CardNET: https://developers.cardnet.com.do/guias/boton-de-pago/
3. Con eso se escribe la clase del proveedor (hereda de `ProveedorDePago` y se registra con `registrar`):
   cómo iniciar el cobro, cómo verificar la respuesta y las notificaciones, y cómo reembolsar.
4. Variables de entorno en Render: `PAGOS_PROVEEDOR_TARJETA` con el código del proveedor y las credenciales
   que indique su documentación. Nunca van en el código ni en la base de datos.
5. Pruebas en el entorno de pruebas del proveedor (aprobado, rechazado, cancelado y notificación repetida) antes
   de usar las credenciales reales.
6. El cobro con tarjeta lo recibe el dueño: esos pedidos nacen con `cobra_el_sitio=True` (en `crear_pedido`) para
   que entren al reparto (Liquidaciones) como cobrados por el sitio.
7. El carrito único: un pago que cubre los pedidos de varias tiendas (cada tienda sigue recibiendo su propio pedido,
   con su numeración, su entrega y su seguimiento).

No se guardan números de tarjeta ni códigos de seguridad en ningún caso: del proveedor solo se conservan la
referencia del pago y el código de autorización.
