# Avisos por WhatsApp

Hay dos formas de avisarle al cliente por WhatsApp cuando cambia su pedido.

## 1. A mano, desde el panel (funciona ya, sin costo)

En el detalle de cada pedido (Panel > Pedidos) está el botón **"Avisar al cliente por WhatsApp"**. Abre WhatsApp
(web o la app) con el chat del cliente y el mensaje del estado actual ya escrito: "Hola Ana, te escribimos de
Multimix RD: tu pedido MMX-2026-00012 va en camino. Míralo aquí: ...". Quien atiende lo revisa y lo envía.

Lo normal es cambiar el estado y, enseguida, tocar el botón.

## 2. Automático, con la API oficial de WhatsApp (opcional)

El sitio puede enviar el aviso solo, cada vez que cambia el estado, con la **WhatsApp Cloud API** de Meta. Mientras
no se configure, queda apagado y en el checkout no aparece la casilla.

WhatsApp solo deja que una empresa escriba primero con una **plantilla aprobada por Meta**, y solo a quien aceptó
recibir mensajes. Por eso el checkout muestra la casilla "Avisarme por WhatsApp cuando cambie mi pedido" y solo se
le escribe a quien la marca (`Pedido.avisos_whatsapp`).

### Pasos

1. Crear una cuenta en Meta Business y una app de tipo "Empresa" en https://developers.facebook.com con el
   producto **WhatsApp**. Registrar el número de la empresa (no puede estar usándose en la app de WhatsApp normal
   al mismo tiempo; lo usual es un número aparte).
2. En **WhatsApp Manager > Plantillas de mensajes**, crear una plantilla de categoría **Utilidad**, idioma
   **Español**, con el nombre `estado_pedido` y este cuerpo (las variables van en este orden):

   ```
   Hola {{1}}, tu pedido {{2}} ahora está: {{3}}. Míralo aquí: {{4}}
   ```

   `{{1}}` es el primer nombre del cliente, `{{2}}` el número de pedido, `{{3}}` el estado ("pagado",
   "enviado", "entregado"...) y `{{4}}` el enlace a la página del pedido. Esperar a que Meta la apruebe.
3. Crear un **token permanente** (usuario del sistema en la configuración del negocio, con permiso
   `whatsapp_business_messaging`) y copiar el **ID del número de teléfono** (no es el número: es el identificador
   que aparece en "Configuración de la API").
4. En Render > multimix-rd > Environment, agregar:

   | Variable | Valor |
   |---|---|
   | `WHATSAPP_TOKEN` | el token permanente |
   | `WHATSAPP_NUMERO_ID` | el ID del número de teléfono |
   | `WHATSAPP_PLANTILLA` | opcional; por defecto `estado_pedido` |
   | `WHATSAPP_IDIOMA` | opcional; por defecto `es` |

   Al guardar, Render vuelve a desplegar y el checkout ya muestra la casilla.

### Costos y registro

Meta cobra cada conversación iniciada por la empresa (las de "Utilidad" son baratas y algunas al mes son
gratis). Cada envío queda en los registros con el número de pedido; si Meta rechaza uno (plantilla sin aprobar,
número sin WhatsApp), el registro dice por qué. Un envío que falla nunca impide el cambio de estado ni el correo.
