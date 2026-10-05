# Facturas de pedidos

Desde la confirmación de un pedido, el cliente puede abrir la imagen PNG de su comprobante y
 guardarla o compartirla. Incluye un QR individual ligado al token UUID del pedido.

- `/pedido/<token>/factura.png` genera el comprobante con los datos y montos guardados en el pedido.
- `/pedido/<token>/verificar/` muestra el número, fecha, total y estado actual para verificar el QR.
- La verificación no publica datos personales ni confirma que el pago haya sido recibido.
- El comprobante indica expresamente que no es un comprobante fiscal.

El QR se codifica al generar la imagen; el servidor necesita la dependencia `qrcode[pil]`.
