-- Esquema de referencia de Multimix RD, generado con `manage.py sqlmigrate` sobre SQLite.
-- NO se ejecuta a mano: en cualquier motor las tablas las crea `python manage.py migrate`.
-- En PostgreSQL o MySQL cambian los tipos (bigint identity, numeric, timestamp with time zone...).
-- Para ver el SQL exacto de tu motor: python manage.py sqlmigrate <app> <migracion>

-- ============================================================
-- core 0001
-- ============================================================
BEGIN;
--
-- Create model ConfiguracionTienda
--
CREATE TABLE "core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(15) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "permitir_contra_entrega" bool NOT NULL);
--
-- Create model CuentaBancaria
--
CREATE TABLE "core_cuentabancaria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "banco" varchar(80) NOT NULL, "tipo_cuenta" varchar(10) NOT NULL, "numero" varchar(30) NOT NULL, "titular" varchar(120) NOT NULL, "cedula_rnc" varchar(20) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), CONSTRAINT "cuenta_banco_numero_unica" UNIQUE ("banco", "numero"));
COMMIT;

-- ============================================================
-- core 0002
-- ============================================================
-- No cambia el esquema: solo los textos por defecto del banner y una correccion de datos
-- (quita de la configuracion el logo o banner cuyo archivo ya no existe).

-- ============================================================
-- catalogo 0001
-- ============================================================
BEGIN;
--
-- Create model Categoria
--
CREATE TABLE "catalogo_categoria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(100) NOT NULL UNIQUE, "descripcion" text NOT NULL, "imagen" varchar(100) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0));
--
-- Create model Producto
--
CREATE TABLE "catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL UNIQUE, "sku" varchar(40) NOT NULL UNIQUE, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model FotoProducto
--
CREATE TABLE "catalogo_fotoproducto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "imagen" varchar(100) NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "principal" bool NOT NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create index producto_activo_creado_idx on field(s) activo, -creado of model producto
--
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
--
-- Create index producto_activo_destacado_idx on field(s) activo, destacado of model producto
--
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
--
-- Create index producto_categoria_activo_idx on field(s) categoria, activo of model producto
--
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
--
-- Create index producto_precio_idx on field(s) precio of model producto
--
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
--
-- Create constraint producto_precio_positivo on model producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL UNIQUE, "sku" varchar(40) NOT NULL UNIQUE, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_fotoproducto_producto_id_f83ae5fd" ON "catalogo_fotoproducto" ("producto_id");
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
--
-- Create constraint producto_oferta_menor_que_precio on model producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL UNIQUE, "sku" varchar(40) NOT NULL UNIQUE, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
--
-- Create constraint producto_reservado_no_supera_almacen on model producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL UNIQUE, "sku" varchar(40) NOT NULL UNIQUE, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
COMMIT;

-- ============================================================
-- catalogo 0002
-- ============================================================
BEGIN;
--
-- Add field texto_busqueda to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "texto_busqueda" text NOT NULL, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL UNIQUE, "sku" varchar(40) NOT NULL UNIQUE, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", '' FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
--
-- Raw Python operation
--
-- THIS OPERATION CANNOT BE WRITTEN AS SQL
COMMIT;

-- ============================================================
-- promociones 0001
-- ============================================================
BEGIN;
--
-- Create model Cupon
--
CREATE TABLE "promociones_cupon" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "codigo" varchar(30) NOT NULL UNIQUE, "tipo" varchar(12) NOT NULL, "valor" decimal NOT NULL, "compra_minima" decimal NOT NULL, "vigente_desde" datetime NULL, "vigente_hasta" datetime NULL, "usos_maximos" integer unsigned NULL CHECK ("usos_maximos" >= 0), "usos_actuales" integer unsigned NOT NULL CHECK ("usos_actuales" >= 0), "activo" bool NOT NULL, CONSTRAINT "cupon_valor_positivo" CHECK ("valor" > '0'), CONSTRAINT "cupon_porcentaje_maximo_100" CHECK ((NOT ("tipo" = 'porcentaje') OR "valor" <= '100')));
COMMIT;

-- ============================================================
-- pedidos 0001
-- ============================================================
BEGIN;
--
-- Create model SecuenciaPedido
--
CREATE TABLE "pedidos_secuenciapedido" ("anio" smallint unsigned NOT NULL PRIMARY KEY CHECK ("anio" >= 0), "ultimo" integer unsigned NOT NULL CHECK ("ultimo" >= 0));
--
-- Create model ZonaEnvio
--
CREATE TABLE "pedidos_zonaenvio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "tarifa" decimal NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), CONSTRAINT "zona_tarifa_no_negativa" CHECK ("tarifa" >= '0'));
--
-- Create model Pedido
--
CREATE TABLE "pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model DetallePedido
--
CREATE TABLE "pedidos_detallepedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre_producto" varchar(150) NOT NULL, "precio_unitario" decimal NOT NULL, "cantidad" integer unsigned NOT NULL CHECK ("cantidad" >= 0), "subtotal" decimal NOT NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "detalle_cantidad_positiva" CHECK ("cantidad" > 0), CONSTRAINT "detalle_producto_unico_por_pedido" UNIQUE ("pedido_id", "producto_id"));
--
-- Create index pedido_estado_creado_idx on field(s) estado, -creado of model pedido
--
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
--
-- Create index pedido_creado_idx on field(s) -creado of model pedido
--
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
--
-- Create index pedido_fecha_pago_idx on field(s) fecha_pago of model pedido
--
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
--
-- Create index pedido_telefono_idx on field(s) telefono of model pedido
--
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
--
-- Create index pedido_ip_creado_idx on field(s) ip, -creado of model pedido
--
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
--
-- Create constraint pedido_envio_requiere_zona on model pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_detallepedido_producto_id_fb78018a" ON "pedidos_detallepedido" ("producto_id");
CREATE INDEX "pedidos_detallepedido_pedido_id_37ae55c6" ON "pedidos_detallepedido" ("pedido_id");
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
--
-- Create constraint pedido_efectivo_recoger_solo_en_tienda on model pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
--
-- Create constraint pedido_montos_no_negativos on model pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
--
-- Create constraint pedido_descuento_no_supera_subtotal on model pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
COMMIT;

-- ============================================================
-- tiendas 0001
-- ============================================================
BEGIN;
--
-- Create model Tienda
--
CREATE TABLE "tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(15) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL);
CREATE TABLE "tiendas_tienda_usuarios" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE UNIQUE INDEX "tiendas_tienda_usuarios_tienda_id_user_id_d3754104_uniq" ON "tiendas_tienda_usuarios" ("tienda_id", "user_id");
CREATE INDEX "tiendas_tienda_usuarios_tienda_id_bccd58f2" ON "tiendas_tienda_usuarios" ("tienda_id");
CREATE INDEX "tiendas_tienda_usuarios_user_id_722c2a37" ON "tiendas_tienda_usuarios" ("user_id");
COMMIT;

-- ============================================================
-- tiendas 0002
-- ============================================================
-- No cambia el esquema: si el sitio ya tenia datos, crea la primera tienda con la marca, los contactos
-- y la forma de cobrar que estaban en la configuracion general (prefijo de pedidos MMX).

-- ============================================================
-- catalogo 0003
-- ============================================================
BEGIN;
--
-- Add field tienda to producto
--
ALTER TABLE "catalogo_producto" ADD COLUMN "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Alter field sku on producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL UNIQUE, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "sku" varchar(40) NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "sku") SELECT "id", "nombre", "slug", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "sku" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "catalogo_producto_tienda_id_cbac6c3f" ON "catalogo_producto" ("tienda_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
--
-- Alter field slug on producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "slug" varchar(170) NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "slug") SELECT "id", "nombre", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "slug" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "catalogo_producto_tienda_id_cbac6c3f" ON "catalogo_producto" ("tienda_id");
CREATE INDEX "catalogo_producto_slug_178d3ecc" ON "catalogo_producto" ("slug");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
--
-- Create index producto_tienda_activo_idx on field(s) tienda, activo, -creado of model producto
--
CREATE INDEX "producto_tienda_activo_idx" ON "catalogo_producto" ("tienda_id", "activo", "creado" DESC);
--
-- Create constraint producto_sku_unico_por_tienda on model producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_slug_178d3ecc" ON "catalogo_producto" ("slug");
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "catalogo_producto_tienda_id_cbac6c3f" ON "catalogo_producto" ("tienda_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
CREATE INDEX "producto_tienda_activo_idx" ON "catalogo_producto" ("tienda_id", "activo", "creado" DESC);
--
-- Create constraint producto_slug_unico_por_tienda on model producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id" FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_slug_178d3ecc" ON "catalogo_producto" ("slug");
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "catalogo_producto_tienda_id_cbac6c3f" ON "catalogo_producto" ("tienda_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
CREATE INDEX "producto_tienda_activo_idx" ON "catalogo_producto" ("tienda_id", "activo", "creado" DESC);
COMMIT;

-- ============================================================
-- catalogo 0004
-- ============================================================
-- No cambia el esquema: los productos que existian pasan a la primera tienda.

-- ============================================================
-- catalogo 0005
-- ============================================================
BEGIN;
--
-- Alter field tienda on producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", coalesce("tienda_id", NULL) FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_tienda_id_cbac6c3f" ON "catalogo_producto" ("tienda_id");
CREATE INDEX "catalogo_producto_slug_178d3ecc" ON "catalogo_producto" ("slug");
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
CREATE INDEX "producto_tienda_activo_idx" ON "catalogo_producto" ("tienda_id", "activo", "creado" DESC);
COMMIT;

-- ============================================================
-- core 0003
-- ============================================================
BEGIN;
--
-- Remove constraint cuenta_banco_numero_unica from model cuentabancaria
--
CREATE TABLE "new__core_cuentabancaria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "banco" varchar(80) NOT NULL, "tipo_cuenta" varchar(10) NOT NULL, "numero" varchar(30) NOT NULL, "titular" varchar(120) NOT NULL, "cedula_rnc" varchar(20) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0));
INSERT INTO "new__core_cuentabancaria" ("id", "banco", "tipo_cuenta", "numero", "titular", "cedula_rnc", "activa", "orden") SELECT "id", "banco", "tipo_cuenta", "numero", "titular", "cedula_rnc", "activa", "orden" FROM "core_cuentabancaria";
DROP TABLE "core_cuentabancaria";
ALTER TABLE "new__core_cuentabancaria" RENAME TO "core_cuentabancaria";
--
-- Add field tienda to cuentabancaria
--
ALTER TABLE "core_cuentabancaria" ADD COLUMN "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Create constraint cuenta_unica_por_tienda on model cuentabancaria
--
CREATE TABLE "new__core_cuentabancaria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "banco" varchar(80) NOT NULL, "tipo_cuenta" varchar(10) NOT NULL, "numero" varchar(30) NOT NULL, "titular" varchar(120) NOT NULL, "cedula_rnc" varchar(20) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "cuenta_unica_por_tienda" UNIQUE ("tienda_id", "banco", "numero"));
INSERT INTO "new__core_cuentabancaria" ("id", "banco", "tipo_cuenta", "numero", "titular", "cedula_rnc", "activa", "orden", "tienda_id") SELECT "id", "banco", "tipo_cuenta", "numero", "titular", "cedula_rnc", "activa", "orden", "tienda_id" FROM "core_cuentabancaria";
DROP TABLE "core_cuentabancaria";
ALTER TABLE "new__core_cuentabancaria" RENAME TO "core_cuentabancaria";
CREATE INDEX "core_cuentabancaria_tienda_id_897acb3e" ON "core_cuentabancaria" ("tienda_id");
COMMIT;

-- ============================================================
-- core 0004
-- ============================================================
-- No cambia el esquema: las cuentas bancarias que existian pasan a la primera tienda.

-- ============================================================
-- core 0005
-- ============================================================
BEGIN;
--
-- Change Meta options on configuraciontienda
--
-- (no-op)
--
-- Remove field direccion_tienda from configuraciontienda
--
ALTER TABLE "core_configuraciontienda" DROP COLUMN "direccion_tienda";
--
-- Remove field permitir_contra_entrega from configuraciontienda
--
ALTER TABLE "core_configuraciontienda" DROP COLUMN "permitir_contra_entrega";
--
-- Alter field nombre on configuraciontienda
--
-- (no-op)
--
-- Alter field tienda on cuentabancaria
--
CREATE TABLE "new__core_cuentabancaria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "banco" varchar(80) NOT NULL, "tipo_cuenta" varchar(10) NOT NULL, "numero" varchar(30) NOT NULL, "titular" varchar(120) NOT NULL, "cedula_rnc" varchar(20) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "cuenta_unica_por_tienda" UNIQUE ("tienda_id", "banco", "numero"));
INSERT INTO "new__core_cuentabancaria" ("id", "banco", "tipo_cuenta", "numero", "titular", "cedula_rnc", "activa", "orden", "tienda_id") SELECT "id", "banco", "tipo_cuenta", "numero", "titular", "cedula_rnc", "activa", "orden", coalesce("tienda_id", NULL) FROM "core_cuentabancaria";
DROP TABLE "core_cuentabancaria";
ALTER TABLE "new__core_cuentabancaria" RENAME TO "core_cuentabancaria";
CREATE INDEX "core_cuentabancaria_tienda_id_897acb3e" ON "core_cuentabancaria" ("tienda_id");
COMMIT;

-- ============================================================
-- promociones 0002
-- ============================================================
BEGIN;
--
-- Add field tienda to cupon
--
ALTER TABLE "promociones_cupon" ADD COLUMN "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Alter field codigo on cupon
--
CREATE TABLE "new__promociones_cupon" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tipo" varchar(12) NOT NULL, "valor" decimal NOT NULL, "compra_minima" decimal NOT NULL, "vigente_desde" datetime NULL, "vigente_hasta" datetime NULL, "usos_maximos" integer unsigned NULL CHECK ("usos_maximos" >= 0), "usos_actuales" integer unsigned NOT NULL CHECK ("usos_actuales" >= 0), "activo" bool NOT NULL, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "codigo" varchar(30) NOT NULL, CONSTRAINT "cupon_valor_positivo" CHECK ("valor" > '0'), CONSTRAINT "cupon_porcentaje_maximo_100" CHECK ((NOT ("tipo" = 'porcentaje') OR "valor" <= '100')));
INSERT INTO "new__promociones_cupon" ("id", "tipo", "valor", "compra_minima", "vigente_desde", "vigente_hasta", "usos_maximos", "usos_actuales", "activo", "tienda_id", "codigo") SELECT "id", "tipo", "valor", "compra_minima", "vigente_desde", "vigente_hasta", "usos_maximos", "usos_actuales", "activo", "tienda_id", "codigo" FROM "promociones_cupon";
DROP TABLE "promociones_cupon";
ALTER TABLE "new__promociones_cupon" RENAME TO "promociones_cupon";
CREATE INDEX "promociones_cupon_tienda_id_8162924a" ON "promociones_cupon" ("tienda_id");
--
-- Create constraint cupon_codigo_unico_por_tienda on model cupon
--
CREATE TABLE "new__promociones_cupon" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "codigo" varchar(30) NOT NULL, "tipo" varchar(12) NOT NULL, "valor" decimal NOT NULL, "compra_minima" decimal NOT NULL, "vigente_desde" datetime NULL, "vigente_hasta" datetime NULL, "usos_maximos" integer unsigned NULL CHECK ("usos_maximos" >= 0), "usos_actuales" integer unsigned NOT NULL CHECK ("usos_actuales" >= 0), "activo" bool NOT NULL, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "cupon_valor_positivo" CHECK ("valor" > '0'), CONSTRAINT "cupon_porcentaje_maximo_100" CHECK ((NOT ("tipo" = 'porcentaje') OR "valor" <= '100')), CONSTRAINT "cupon_codigo_unico_por_tienda" UNIQUE ("tienda_id", "codigo"));
INSERT INTO "new__promociones_cupon" ("id", "codigo", "tipo", "valor", "compra_minima", "vigente_desde", "vigente_hasta", "usos_maximos", "usos_actuales", "activo", "tienda_id") SELECT "id", "codigo", "tipo", "valor", "compra_minima", "vigente_desde", "vigente_hasta", "usos_maximos", "usos_actuales", "activo", "tienda_id" FROM "promociones_cupon";
DROP TABLE "promociones_cupon";
ALTER TABLE "new__promociones_cupon" RENAME TO "promociones_cupon";
CREATE INDEX "promociones_cupon_tienda_id_8162924a" ON "promociones_cupon" ("tienda_id");
COMMIT;

-- ============================================================
-- pedidos 0002
-- ============================================================
BEGIN;
--
-- Create model SecuenciaTienda
--
CREATE TABLE "pedidos_secuenciatienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "anio" smallint unsigned NOT NULL CHECK ("anio" >= 0), "ultimo" integer unsigned NOT NULL CHECK ("ultimo" >= 0));
--
-- Add field tienda to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Add field tienda to zonaenvio
--
ALTER TABLE "pedidos_zonaenvio" ADD COLUMN "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Alter field nombre on zonaenvio
--
CREATE TABLE "new__pedidos_zonaenvio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tarifa" decimal NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "nombre" varchar(80) NOT NULL, CONSTRAINT "zona_tarifa_no_negativa" CHECK ("tarifa" >= '0'));
INSERT INTO "new__pedidos_zonaenvio" ("id", "tarifa", "activa", "orden", "tienda_id", "nombre") SELECT "id", "tarifa", "activa", "orden", "tienda_id", "nombre" FROM "pedidos_zonaenvio";
DROP TABLE "pedidos_zonaenvio";
ALTER TABLE "new__pedidos_zonaenvio" RENAME TO "pedidos_zonaenvio";
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_zonaenvio_tienda_id_f1f92876" ON "pedidos_zonaenvio" ("tienda_id");
--
-- Create index pedido_tienda_creado_idx on field(s) tienda, -creado of model pedido
--
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Create constraint zona_nombre_unico_por_tienda on model zonaenvio
--
CREATE TABLE "new__pedidos_zonaenvio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "tarifa" decimal NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "zona_tarifa_no_negativa" CHECK ("tarifa" >= '0'), CONSTRAINT "zona_nombre_unico_por_tienda" UNIQUE ("tienda_id", "nombre"));
INSERT INTO "new__pedidos_zonaenvio" ("id", "nombre", "tarifa", "activa", "orden", "tienda_id") SELECT "id", "nombre", "tarifa", "activa", "orden", "tienda_id" FROM "pedidos_zonaenvio";
DROP TABLE "pedidos_zonaenvio";
ALTER TABLE "new__pedidos_zonaenvio" RENAME TO "pedidos_zonaenvio";
CREATE INDEX "pedidos_zonaenvio_tienda_id_f1f92876" ON "pedidos_zonaenvio" ("tienda_id");
--
-- Add field tienda to secuenciatienda
--
CREATE TABLE "new__pedidos_secuenciatienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "anio" smallint unsigned NOT NULL CHECK ("anio" >= 0), "ultimo" integer unsigned NOT NULL CHECK ("ultimo" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
INSERT INTO "new__pedidos_secuenciatienda" ("id", "anio", "ultimo", "tienda_id") SELECT "id", "anio", "ultimo", NULL FROM "pedidos_secuenciatienda";
DROP TABLE "pedidos_secuenciatienda";
ALTER TABLE "new__pedidos_secuenciatienda" RENAME TO "pedidos_secuenciatienda";
CREATE INDEX "pedidos_secuenciatienda_tienda_id_a9a32d8c" ON "pedidos_secuenciatienda" ("tienda_id");
--
-- Create constraint secuencia_unica_por_tienda_y_anio on model secuenciatienda
--
CREATE TABLE "new__pedidos_secuenciatienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "anio" smallint unsigned NOT NULL CHECK ("anio" >= 0), "ultimo" integer unsigned NOT NULL CHECK ("ultimo" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "secuencia_unica_por_tienda_y_anio" UNIQUE ("tienda_id", "anio"));
INSERT INTO "new__pedidos_secuenciatienda" ("id", "anio", "ultimo", "tienda_id") SELECT "id", "anio", "ultimo", "tienda_id" FROM "pedidos_secuenciatienda";
DROP TABLE "pedidos_secuenciatienda";
ALTER TABLE "new__pedidos_secuenciatienda" RENAME TO "pedidos_secuenciatienda";
CREATE INDEX "pedidos_secuenciatienda_tienda_id_a9a32d8c" ON "pedidos_secuenciatienda" ("tienda_id");
COMMIT;

-- ============================================================
-- pedidos 0003
-- ============================================================
-- No cambia el esquema: los pedidos y las zonas que existian pasan a la primera tienda, y el contador
-- de pedidos por año se copia al contador por tienda y año.

-- ============================================================
-- pedidos 0004
-- ============================================================
BEGIN;
--
-- Delete model SecuenciaPedido
--
DROP TABLE "pedidos_secuenciapedido";
--
-- Alter field tienda on pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", coalesce("tienda_id", NULL) FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Alter field tienda on zonaenvio
--
CREATE TABLE "new__pedidos_zonaenvio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "tarifa" decimal NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "zona_tarifa_no_negativa" CHECK ("tarifa" >= '0'), CONSTRAINT "zona_nombre_unico_por_tienda" UNIQUE ("tienda_id", "nombre"));
INSERT INTO "new__pedidos_zonaenvio" ("id", "nombre", "tarifa", "activa", "orden", "tienda_id") SELECT "id", "nombre", "tarifa", "activa", "orden", coalesce("tienda_id", NULL) FROM "pedidos_zonaenvio";
DROP TABLE "pedidos_zonaenvio";
ALTER TABLE "new__pedidos_zonaenvio" RENAME TO "pedidos_zonaenvio";
CREATE INDEX "pedidos_zonaenvio_tienda_id_f1f92876" ON "pedidos_zonaenvio" ("tienda_id");
COMMIT;

-- ============================================================
-- promociones 0003
-- ============================================================
-- No cambia el esquema: los cupones que existian pasan a la primera tienda.

-- ============================================================
-- promociones 0004
-- ============================================================
BEGIN;
--
-- Alter field tienda on cupon
--
CREATE TABLE "new__promociones_cupon" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "codigo" varchar(30) NOT NULL, "tipo" varchar(12) NOT NULL, "valor" decimal NOT NULL, "compra_minima" decimal NOT NULL, "vigente_desde" datetime NULL, "vigente_hasta" datetime NULL, "usos_maximos" integer unsigned NULL CHECK ("usos_maximos" >= 0), "usos_actuales" integer unsigned NOT NULL CHECK ("usos_actuales" >= 0), "activo" bool NOT NULL, CONSTRAINT "cupon_valor_positivo" CHECK ("valor" > '0'), CONSTRAINT "cupon_porcentaje_maximo_100" CHECK ((NOT ("tipo" = 'porcentaje') OR "valor" <= '100')), CONSTRAINT "cupon_codigo_unico_por_tienda" UNIQUE ("tienda_id", "codigo"));
INSERT INTO "new__promociones_cupon" ("id", "codigo", "tipo", "valor", "compra_minima", "vigente_desde", "vigente_hasta", "usos_maximos", "usos_actuales", "activo", "tienda_id") SELECT "id", "codigo", "tipo", "valor", "compra_minima", "vigente_desde", "vigente_hasta", "usos_maximos", "usos_actuales", "activo", coalesce("tienda_id", NULL) FROM "promociones_cupon";
DROP TABLE "promociones_cupon";
ALTER TABLE "new__promociones_cupon" RENAME TO "promociones_cupon";
CREATE INDEX "promociones_cupon_tienda_id_8162924a" ON "promociones_cupon" ("tienda_id");
COMMIT;

-- ============================================================
-- core 0006
-- ============================================================
BEGIN;
--
-- Rename field banner_subtitulo on configuraciontienda to descripcion
--
ALTER TABLE "core_configuraciontienda" RENAME COLUMN "banner_subtitulo" TO "descripcion";
--
-- Remove field banner_titulo from configuraciontienda
--
ALTER TABLE "core_configuraciontienda" DROP COLUMN "banner_titulo";
--
-- Remove field banner_texto_boton from configuraciontienda
--
ALTER TABLE "core_configuraciontienda" DROP COLUMN "banner_texto_boton";
--
-- Remove field banner_imagen from configuraciontienda
--
ALTER TABLE "core_configuraciontienda" DROP COLUMN "banner_imagen";
COMMIT;

-- ============================================================
-- core 0007
-- ============================================================
BEGIN;
--
-- Alter field descripcion on configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "descripcion" varchar(220) NOT NULL, "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(15) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL);
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion" FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";
--
-- Alter field logo on configuraciontienda
--
-- (no-op)
--
-- Alter field whatsapp on configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "descripcion" varchar(220) NOT NULL, "whatsapp" varchar(20) NOT NULL);
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "whatsapp") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "whatsapp" FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";
COMMIT;

-- ============================================================
-- core 0008
-- ============================================================
-- No cambia el esquema: reemplaza el lema de la tienda original por la descripcion del sitio y pone el
-- codigo de pais a los WhatsApp guardados con 10 digitos.

-- ============================================================
-- tiendas 0003
-- ============================================================
BEGIN;
--
-- Alter field banner_imagen on tienda
--
-- (no-op)
--
-- Alter field logo on tienda
--
-- (no-op)
--
-- Alter field whatsapp on tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL, "whatsapp" varchar(20) NOT NULL);
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "whatsapp") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "whatsapp" FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";
COMMIT;

-- ============================================================
-- tiendas 0004
-- ============================================================
-- No cambia el esquema: pone el codigo de pais a los WhatsApp guardados con 10 digitos.
