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

-- ============================================================
-- catalogo 0006
-- ============================================================
-- No cambia el esquema: las imagenes pasan a guardarse con un nombre generado (core.archivos.NombreUnico).

-- ============================================================
-- core 0009
-- ============================================================
-- No cambia el esquema: las imagenes pasan a guardarse con un nombre generado (core.archivos.NombreUnico).

-- ============================================================
-- tiendas 0005
-- ============================================================
-- No cambia el esquema: las imagenes pasan a guardarse con un nombre generado (core.archivos.NombreUnico).

-- ============================================================
-- catalogo 0007
-- ============================================================
--
-- Add field controla_stock to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "controla_stock" bool NOT NULL, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", 0 FROM "catalogo_producto";
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
-- Add field disponibilidad to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "controla_stock" bool NOT NULL, "disponibilidad" varchar(15) NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", 'disponible' FROM "catalogo_producto";
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
-- Create index producto_disponibilidad_idx on field(s) tienda, disponibilidad of model producto
--
CREATE INDEX "producto_disponibilidad_idx" ON "catalogo_producto" ("tienda_id", "disponibilidad");

-- ============================================================
-- catalogo 0008
-- ============================================================
-- No cambia el esquema: la tienda que ya tenia unidades cargadas sigue llevando inventario (controla_stock).

-- ============================================================
-- pedidos 0005
-- ============================================================
--
-- Add field reserva_stock to detallepedido
--
CREATE TABLE "new__pedidos_detallepedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "reserva_stock" bool NOT NULL, "nombre_producto" varchar(150) NOT NULL, "precio_unitario" decimal NOT NULL, "cantidad" integer unsigned NOT NULL CHECK ("cantidad" >= 0), "subtotal" decimal NOT NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "detalle_cantidad_positiva" CHECK ("cantidad" > 0), CONSTRAINT "detalle_producto_unico_por_pedido" UNIQUE ("pedido_id", "producto_id"));
INSERT INTO "new__pedidos_detallepedido" ("id", "nombre_producto", "precio_unitario", "cantidad", "subtotal", "producto_id", "pedido_id", "reserva_stock") SELECT "id", "nombre_producto", "precio_unitario", "cantidad", "subtotal", "producto_id", "pedido_id", 0 FROM "pedidos_detallepedido";
DROP TABLE "pedidos_detallepedido";
ALTER TABLE "new__pedidos_detallepedido" RENAME TO "pedidos_detallepedido";
CREATE INDEX "pedidos_detallepedido_producto_id_fb78018a" ON "pedidos_detallepedido" ("producto_id");
CREATE INDEX "pedidos_detallepedido_pedido_id_37ae55c6" ON "pedidos_detallepedido" ("pedido_id");

-- ============================================================
-- pedidos 0006
-- ============================================================
-- No cambia el esquema: las lineas de los pedidos que ya existian quedan con reserva_stock.

-- ============================================================
-- catalogo 0009
-- ============================================================
-- No cambia el esquema: en las tiendas sin pedidos, los productos en cero dejan de llevar inventario.

-- ============================================================
-- catalogo 0010
-- ============================================================
--
-- Add field marca to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "marca" varchar(60) NOT NULL, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "controla_stock" bool NOT NULL, "disponibilidad" varchar(15) NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", '' FROM "catalogo_producto";
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
CREATE INDEX "producto_disponibilidad_idx" ON "catalogo_producto" ("tienda_id", "disponibilidad");
--
-- Alter field texto_busqueda on producto
--
-- (no-op)

-- ============================================================
-- catalogo 0011
-- ============================================================
--
-- Add field exento_itbis to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "exento_itbis" bool NOT NULL, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "controla_stock" bool NOT NULL, "disponibilidad" varchar(15) NOT NULL, "marca" varchar(60) NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", 0 FROM "catalogo_producto";
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
CREATE INDEX "producto_disponibilidad_idx" ON "catalogo_producto" ("tienda_id", "disponibilidad");

-- ============================================================
-- tiendas 0006
-- ============================================================
--
-- Add field itbis_porcentaje to tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "itbis_porcentaje" decimal NOT NULL, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL);
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", '18.00' FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";

-- ============================================================
-- pedidos 0007
-- ============================================================
--
-- Remove constraint pedido_montos_no_negativos from model pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Add field impuesto to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", '0.00' FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Add field porcentaje_impuesto to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", '0.00' FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Add field sector to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", '' FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Create constraint pedido_montos_no_negativos on model pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0' AND "impuesto" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);

-- ============================================================
-- catalogo 0012, core 0010 y 0011
-- ============================================================
-- No cambian el esquema: marca de los productos de Amway segun su linea y nueva descripcion del sitio.

-- ============================================================
-- pagos 0001
-- ============================================================
--
-- Create model Pago
--
CREATE TABLE "pagos_pago" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "referencia" varchar(40) NOT NULL UNIQUE, "metodo" varchar(20) NOT NULL, "proveedor" varchar(20) NOT NULL, "monto" decimal NOT NULL, "estado" varchar(12) NOT NULL, "comprobante" varchar(100) NOT NULL, "referencia_cliente" varchar(60) NOT NULL, "codigo_autorizacion" varchar(40) NOT NULL, "respuesta_proveedor" text NOT NULL CHECK ((JSON_VALID("respuesta_proveedor") OR "respuesta_proveedor" IS NULL)), "nota" varchar(255) NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "revisado_en" datetime NULL, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, "revisado_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pago_monto_no_negativo" CHECK ("monto" >= '0'));
CREATE UNIQUE INDEX "un_pago_aprobado_por_pedido" ON "pagos_pago" ("pedido_id") WHERE "estado" = 'aprobado';
CREATE INDEX "pagos_pago_pedido_id_b527cca2" ON "pagos_pago" ("pedido_id");
CREATE INDEX "pagos_pago_revisado_por_id_bf842120" ON "pagos_pago" ("revisado_por_id");
CREATE INDEX "pagos_pago_tienda_id_0acba72a" ON "pagos_pago" ("tienda_id");
CREATE INDEX "pago_tienda_estado_idx" ON "pagos_pago" ("tienda_id", "estado", "creado" DESC);

-- ============================================================
-- tiendas 0007 y 0008
-- ============================================================
-- El ITBIS queda en 0 por defecto y en todas las tiendas (no cambia la forma de la tabla).

-- ============================================================
-- clientes 0001
-- ============================================================
--
-- Create model Perfil
--
CREATE TABLE "clientes_perfil" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "telefono" varchar(10) NOT NULL, "sector" varchar(80) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "usuario_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- ============================================================
-- pedidos 0008
-- ============================================================
--
-- Add field cliente to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "cliente_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "pedidos_pedido_cliente_id_84f4fc73" ON "pedidos_pedido" ("cliente_id");

-- ============================================================
-- catalogo 0013
-- ============================================================
--
-- Add field padre to categoria
--
ALTER TABLE "catalogo_categoria" ADD COLUMN "padre_id" bigint NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "catalogo_categoria_padre_id_05e7ff80" ON "catalogo_categoria" ("padre_id");

-- ============================================================
-- tiendas 0009
-- ============================================================
--
-- Create model Banner
--
CREATE TABLE "tiendas_banner" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "titulo" varchar(120) NOT NULL, "subtitulo" varchar(220) NOT NULL, "imagen" varchar(100) NOT NULL, "texto_boton" varchar(40) NOT NULL, "enlace" varchar(255) NOT NULL, "activo" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "vigente_desde" datetime NULL, "vigente_hasta" datetime NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "tiendas_banner_tienda_id_1d5d0535" ON "tiendas_banner" ("tienda_id");

-- ============================================================
-- core 0012
-- ============================================================
--
-- Add field dias_devolucion to configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "dias_devolucion" smallint unsigned NOT NULL CHECK ("dias_devolucion" >= 0), "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "descripcion" varchar(220) NOT NULL);
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", 7 FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";

-- ============================================================
-- core 0013
-- ============================================================
--
-- Create model PaginaInformativa
--
CREATE TABLE "core_paginainformativa" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "slug" varchar(60) NOT NULL UNIQUE, "titulo" varchar(120) NOT NULL, "contenido" text NOT NULL, "publicada" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "actualizado" datetime NOT NULL);
--
-- Create model PreguntaFrecuente
--
CREATE TABLE "core_preguntafrecuente" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "pregunta" varchar(200) NOT NULL, "respuesta" text NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0));

-- ============================================================
-- opiniones 0001
-- ============================================================
--
-- Create model Resena
--
CREATE TABLE "opiniones_resena" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "estrellas" smallint unsigned NOT NULL CHECK ("estrellas" >= 0), "comentario" text NOT NULL, "estado" varchar(10) NOT NULL, "compra_verificada" bool NOT NULL, "creado" datetime NOT NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "una_resena_por_cliente_y_producto" UNIQUE ("producto_id", "usuario_id"), CONSTRAINT "resena_de_1_a_5_estrellas" CHECK (("estrellas" >= 1 AND "estrellas" <= 5)));
CREATE INDEX "opiniones_resena_producto_id_40d90b99" ON "opiniones_resena" ("producto_id");
CREATE INDEX "opiniones_resena_tienda_id_32173929" ON "opiniones_resena" ("tienda_id");
CREATE INDEX "opiniones_resena_usuario_id_5c64a8a1" ON "opiniones_resena" ("usuario_id");
CREATE INDEX "resena_producto_estado_idx" ON "opiniones_resena" ("producto_id", "estado", "creado" DESC);

-- ============================================================
-- clientes 0002
-- ============================================================
--
-- Create model Favorito
--
CREATE TABLE "clientes_favorito" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "creado" datetime NOT NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "favorito_unico_por_cliente" UNIQUE ("usuario_id", "producto_id"));
CREATE INDEX "clientes_favorito_producto_id_230fa48c" ON "clientes_favorito" ("producto_id");
CREATE INDEX "clientes_favorito_usuario_id_f5486def" ON "clientes_favorito" ("usuario_id");

-- ============================================================
-- pedidos 0009
-- ============================================================
--
-- Add field numero_seguimiento to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero_seguimiento" varchar(60) NOT NULL, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, "cliente_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0' AND "impuesto" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", '' FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_pedido_cliente_id_84f4fc73" ON "pedidos_pedido" ("cliente_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Add field transportista to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(10) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, "cliente_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "numero_seguimiento" varchar(60) NOT NULL, "transportista" varchar(60) NOT NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0' AND "impuesto" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", '' FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_pedido_cliente_id_84f4fc73" ON "pedidos_pedido" ("cliente_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Alter field estado on pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, "cliente_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "numero_seguimiento" varchar(60) NOT NULL, "transportista" varchar(60) NOT NULL, "estado" varchar(12) NOT NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0' AND "impuesto" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista", "estado") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista", "estado" FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_pedido_cliente_id_84f4fc73" ON "pedidos_pedido" ("cliente_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
--
-- Create model EventoPedido
--
CREATE TABLE "pedidos_eventopedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "estado" varchar(12) NOT NULL, "nota" varchar(255) NOT NULL, "creado" datetime NOT NULL, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model SolicitudDevolucion
--
CREATE TABLE "pedidos_solicituddevolucion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "motivo" text NOT NULL, "estado" varchar(10) NOT NULL, "respuesta" varchar(255) NOT NULL, "creado" datetime NOT NULL, "resuelto_en" datetime NULL, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, "resuelto_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "pedidos_eventopedido_pedido_id_cd43f084" ON "pedidos_eventopedido" ("pedido_id");
CREATE INDEX "pedidos_eventopedido_usuario_id_0ca0fa47" ON "pedidos_eventopedido" ("usuario_id");
CREATE INDEX "pedidos_solicituddevolucion_pedido_id_1c5a66f4" ON "pedidos_solicituddevolucion" ("pedido_id");
CREATE INDEX "pedidos_solicituddevolucion_resuelto_por_id_ca13a7d3" ON "pedidos_solicituddevolucion" ("resuelto_por_id");
CREATE INDEX "pedidos_solicituddevolucion_tienda_id_7b6ba42c" ON "pedidos_solicituddevolucion" ("tienda_id");

-- ============================================================
-- core 0014
-- ============================================================
-- No cambia el esquema: crea las paginas de politicas, vacias y sin publicar.

-- ============================================================
-- tiendas 0010
-- ============================================================
--
-- Add field comision_porcentaje to tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "comision_porcentaje" decimal NOT NULL, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL, "itbis_porcentaje" decimal NOT NULL);
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", '0.00' FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";
--
-- Add field el_sitio_cobra to tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL, "itbis_porcentaje" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "el_sitio_cobra" bool NOT NULL);
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", "el_sitio_cobra") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", 0 FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";

-- ============================================================
-- pagos 0002
-- ============================================================
--
-- Create model Liquidacion
--
CREATE TABLE "pagos_liquidacion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "creada" datetime NOT NULL, "pedidos_incluidos" integer unsigned NOT NULL CHECK ("pedidos_incluidos" >= 0), "ventas" decimal NOT NULL, "cobrado_por_el_sitio" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "comision" decimal NOT NULL, "ajustes" decimal NOT NULL, "monto" decimal NOT NULL, "nota" varchar(255) NOT NULL, "creada_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "pagos_liquidacion_creada_por_id_dc71ed1a" ON "pagos_liquidacion" ("creada_por_id");
CREATE INDEX "pagos_liquidacion_tienda_id_b32bdd81" ON "pagos_liquidacion" ("tienda_id");

-- ============================================================
-- pedidos 0010
-- ============================================================
--
-- Add field ajuste_liquidacion to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "ajuste_liquidacion_id" bigint NULL REFERENCES "pagos_liquidacion" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Add field liquidacion to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "liquidacion_id" bigint NULL REFERENCES "pagos_liquidacion" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Add field monto_liquidado to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "monto_liquidado" decimal NULL;
CREATE INDEX "pedidos_pedido_ajuste_liquidacion_id_f93a0f71" ON "pedidos_pedido" ("ajuste_liquidacion_id");
CREATE INDEX "pedidos_pedido_liquidacion_id_b6b436e1" ON "pedidos_pedido" ("liquidacion_id");

-- ============================================================
-- pagos 0003
-- ============================================================
--
-- Add field costo_transferencia to liquidacion
--
CREATE TABLE "new__pagos_liquidacion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "costo_transferencia" decimal NOT NULL, "creada" datetime NOT NULL, "pedidos_incluidos" integer unsigned NOT NULL CHECK ("pedidos_incluidos" >= 0), "ventas" decimal NOT NULL, "cobrado_por_el_sitio" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "comision" decimal NOT NULL, "ajustes" decimal NOT NULL, "monto" decimal NOT NULL, "nota" varchar(255) NOT NULL, "creada_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
INSERT INTO "new__pagos_liquidacion" ("id", "creada", "pedidos_incluidos", "ventas", "cobrado_por_el_sitio", "comision_porcentaje", "comision", "ajustes", "monto", "nota", "creada_por_id", "tienda_id", "costo_transferencia") SELECT "id", "creada", "pedidos_incluidos", "ventas", "cobrado_por_el_sitio", "comision_porcentaje", "comision", "ajustes", "monto", "nota", "creada_por_id", "tienda_id", '0' FROM "pagos_liquidacion";
DROP TABLE "pagos_liquidacion";
ALTER TABLE "new__pagos_liquidacion" RENAME TO "pagos_liquidacion";
CREATE INDEX "pagos_liquidacion_creada_por_id_dc71ed1a" ON "pagos_liquidacion" ("creada_por_id");
CREATE INDEX "pagos_liquidacion_tienda_id_b32bdd81" ON "pagos_liquidacion" ("tienda_id");
--
-- Alter field monto on liquidacion
--
-- (no-op)

-- ============================================================
-- core 0016
-- ============================================================
--
-- Create model CuentaDelSitio
--
CREATE TABLE "core_cuentadelsitio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "banco" varchar(80) NOT NULL, "tipo_cuenta" varchar(10) NOT NULL, "numero" varchar(30) NOT NULL, "titular" varchar(120) NOT NULL, "cedula_rnc" varchar(20) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), CONSTRAINT "cuenta_del_sitio_unica" UNIQUE ("banco", "numero"));

-- ============================================================
-- pedidos 0011
-- ============================================================
--
-- Add field cobra_el_sitio to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "cobra_el_sitio" bool NOT NULL, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(12) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, "cliente_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "numero_seguimiento" varchar(60) NOT NULL, "transportista" varchar(60) NOT NULL, "ajuste_liquidacion_id" bigint NULL REFERENCES "pagos_liquidacion" ("id") DEFERRABLE INITIALLY DEFERRED, "liquidacion_id" bigint NULL REFERENCES "pagos_liquidacion" ("id") DEFERRABLE INITIALLY DEFERRED, "monto_liquidado" decimal NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0' AND "impuesto" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista", "ajuste_liquidacion_id", "liquidacion_id", "monto_liquidado", "cobra_el_sitio") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista", "ajuste_liquidacion_id", "liquidacion_id", "monto_liquidado", 0 FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_pedido_cliente_id_84f4fc73" ON "pedidos_pedido" ("cliente_id");
CREATE INDEX "pedidos_pedido_ajuste_liquidacion_id_f93a0f71" ON "pedidos_pedido" ("ajuste_liquidacion_id");
CREATE INDEX "pedidos_pedido_liquidacion_id_b6b436e1" ON "pedidos_pedido" ("liquidacion_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);

-- ============================================================
-- pagos 0004
-- ============================================================
--
-- Add field cobrado_por_la_tienda to liquidacion
--
CREATE TABLE "new__pagos_liquidacion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "cobrado_por_la_tienda" decimal NOT NULL, "creada" datetime NOT NULL, "pedidos_incluidos" integer unsigned NOT NULL CHECK ("pedidos_incluidos" >= 0), "ventas" decimal NOT NULL, "cobrado_por_el_sitio" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "comision" decimal NOT NULL, "ajustes" decimal NOT NULL, "monto" decimal NOT NULL, "nota" varchar(255) NOT NULL, "creada_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "costo_transferencia" decimal NOT NULL);
INSERT INTO "new__pagos_liquidacion" ("id", "creada", "pedidos_incluidos", "ventas", "cobrado_por_el_sitio", "comision_porcentaje", "comision", "ajustes", "monto", "nota", "creada_por_id", "tienda_id", "costo_transferencia", "cobrado_por_la_tienda") SELECT "id", "creada", "pedidos_incluidos", "ventas", "cobrado_por_el_sitio", "comision_porcentaje", "comision", "ajustes", "monto", "nota", "creada_por_id", "tienda_id", "costo_transferencia", '0' FROM "pagos_liquidacion";
DROP TABLE "pagos_liquidacion";
ALTER TABLE "new__pagos_liquidacion" RENAME TO "pagos_liquidacion";
CREATE INDEX "pagos_liquidacion_creada_por_id_dc71ed1a" ON "pagos_liquidacion" ("creada_por_id");
CREATE INDEX "pagos_liquidacion_tienda_id_b32bdd81" ON "pagos_liquidacion" ("tienda_id");
--
-- Add field comision_de_lo_cobrado_por_la_tienda to liquidacion
--
CREATE TABLE "new__pagos_liquidacion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "creada" datetime NOT NULL, "pedidos_incluidos" integer unsigned NOT NULL CHECK ("pedidos_incluidos" >= 0), "ventas" decimal NOT NULL, "cobrado_por_el_sitio" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "comision" decimal NOT NULL, "ajustes" decimal NOT NULL, "monto" decimal NOT NULL, "nota" varchar(255) NOT NULL, "creada_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "costo_transferencia" decimal NOT NULL, "cobrado_por_la_tienda" decimal NOT NULL, "comision_de_lo_cobrado_por_la_tienda" decimal NOT NULL);
INSERT INTO "new__pagos_liquidacion" ("id", "creada", "pedidos_incluidos", "ventas", "cobrado_por_el_sitio", "comision_porcentaje", "comision", "ajustes", "monto", "nota", "creada_por_id", "tienda_id", "costo_transferencia", "cobrado_por_la_tienda", "comision_de_lo_cobrado_por_la_tienda") SELECT "id", "creada", "pedidos_incluidos", "ventas", "cobrado_por_el_sitio", "comision_porcentaje", "comision", "ajustes", "monto", "nota", "creada_por_id", "tienda_id", "costo_transferencia", "cobrado_por_la_tienda", '0' FROM "pagos_liquidacion";
DROP TABLE "pagos_liquidacion";
ALTER TABLE "new__pagos_liquidacion" RENAME TO "pagos_liquidacion";
CREATE INDEX "pagos_liquidacion_creada_por_id_dc71ed1a" ON "pagos_liquidacion" ("creada_por_id");
CREATE INDEX "pagos_liquidacion_tienda_id_b32bdd81" ON "pagos_liquidacion" ("tienda_id");

-- ============================================================
-- core 0018
-- ============================================================
--
-- Change Meta options on cuentadelsitio
--
-- (no-op)
--
-- Delete model CuentaBancaria
--
DROP TABLE "core_cuentabancaria";

-- ============================================================
-- tiendas 0012
-- ============================================================
--
-- Remove field el_sitio_cobra from tienda
--
ALTER TABLE "tiendas_tienda" DROP COLUMN "el_sitio_cobra";

-- ============================================================
-- clientes 0003
-- ============================================================
BEGIN;
--
-- Add field correo_verificado to perfil
--
CREATE TABLE "new__clientes_perfil" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "correo_verificado" bool NOT NULL, "telefono" varchar(10) NOT NULL, "sector" varchar(80) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "usuario_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
INSERT INTO "new__clientes_perfil" ("id", "telefono", "sector", "direccion", "referencia", "usuario_id", "correo_verificado") SELECT "id", "telefono", "sector", "direccion", "referencia", "usuario_id", 0 FROM "clientes_perfil";
DROP TABLE "clientes_perfil";
ALTER TABLE "new__clientes_perfil" RENAME TO "clientes_perfil";
COMMIT;

-- ============================================================
-- core 0019
-- ============================================================
BEGIN;
--
-- Create model Intento
--
CREATE TABLE "core_intento" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "clave" varchar(64) NOT NULL, "creado" datetime NOT NULL);
CREATE INDEX "core_intento_clave_67dffd24" ON "core_intento" ("clave");
CREATE INDEX "core_intento_creado_258480fd" ON "core_intento" ("creado");
COMMIT;

-- ============================================================
-- pagos 0006
-- ============================================================
BEGIN;
--
-- Add field comprobante_privado to pago
--
CREATE TABLE "new__pagos_pago" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "comprobante_privado" bool NOT NULL, "referencia" varchar(40) NOT NULL UNIQUE, "metodo" varchar(20) NOT NULL, "proveedor" varchar(20) NOT NULL, "monto" decimal NOT NULL, "estado" varchar(12) NOT NULL, "comprobante" varchar(100) NOT NULL, "referencia_cliente" varchar(60) NOT NULL, "codigo_autorizacion" varchar(40) NOT NULL, "respuesta_proveedor" text NOT NULL CHECK ((JSON_VALID("respuesta_proveedor") OR "respuesta_proveedor" IS NULL)), "nota" varchar(255) NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "revisado_en" datetime NULL, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, "revisado_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "pago_monto_no_negativo" CHECK ("monto" >= '0'));
INSERT INTO "new__pagos_pago" ("id", "referencia", "metodo", "proveedor", "monto", "estado", "comprobante", "referencia_cliente", "codigo_autorizacion", "respuesta_proveedor", "nota", "creado", "actualizado", "revisado_en", "pedido_id", "revisado_por_id", "tienda_id", "comprobante_privado") SELECT "id", "referencia", "metodo", "proveedor", "monto", "estado", "comprobante", "referencia_cliente", "codigo_autorizacion", "respuesta_proveedor", "nota", "creado", "actualizado", "revisado_en", "pedido_id", "revisado_por_id", "tienda_id", 0 FROM "pagos_pago";
DROP TABLE "pagos_pago";
ALTER TABLE "new__pagos_pago" RENAME TO "pagos_pago";
CREATE UNIQUE INDEX "un_pago_aprobado_por_pedido" ON "pagos_pago" ("pedido_id") WHERE "estado" = 'aprobado';
CREATE INDEX "pagos_pago_pedido_id_b527cca2" ON "pagos_pago" ("pedido_id");
CREATE INDEX "pagos_pago_revisado_por_id_bf842120" ON "pagos_pago" ("revisado_por_id");
CREATE INDEX "pagos_pago_tienda_id_0acba72a" ON "pagos_pago" ("tienda_id");
CREATE INDEX "pago_tienda_estado_idx" ON "pagos_pago" ("tienda_id", "estado", "creado" DESC);
--
-- Alter field cobrado_por_la_tienda on liquidacion
--
-- (no-op)
--
-- Alter field comprobante on pago
--
CREATE TABLE "new__pagos_pago" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "referencia" varchar(40) NOT NULL UNIQUE, "metodo" varchar(20) NOT NULL, "proveedor" varchar(20) NOT NULL, "monto" decimal NOT NULL, "estado" varchar(12) NOT NULL, "referencia_cliente" varchar(60) NOT NULL, "codigo_autorizacion" varchar(40) NOT NULL, "respuesta_proveedor" text NOT NULL CHECK ((JSON_VALID("respuesta_proveedor") OR "respuesta_proveedor" IS NULL)), "nota" varchar(255) NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "revisado_en" datetime NULL, "pedido_id" bigint NOT NULL REFERENCES "pedidos_pedido" ("id") DEFERRABLE INITIALLY DEFERRED, "revisado_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "comprobante_privado" bool NOT NULL, "comprobante" varchar(100) NOT NULL, CONSTRAINT "pago_monto_no_negativo" CHECK ("monto" >= '0'));
INSERT INTO "new__pagos_pago" ("id", "referencia", "metodo", "proveedor", "monto", "estado", "referencia_cliente", "codigo_autorizacion", "respuesta_proveedor", "nota", "creado", "actualizado", "revisado_en", "pedido_id", "revisado_por_id", "tienda_id", "comprobante_privado", "comprobante") SELECT "id", "referencia", "metodo", "proveedor", "monto", "estado", "referencia_cliente", "codigo_autorizacion", "respuesta_proveedor", "nota", "creado", "actualizado", "revisado_en", "pedido_id", "revisado_por_id", "tienda_id", "comprobante_privado", "comprobante" FROM "pagos_pago";
DROP TABLE "pagos_pago";
ALTER TABLE "new__pagos_pago" RENAME TO "pagos_pago";
CREATE UNIQUE INDEX "un_pago_aprobado_por_pedido" ON "pagos_pago" ("pedido_id") WHERE "estado" = 'aprobado';
CREATE INDEX "pagos_pago_pedido_id_b527cca2" ON "pagos_pago" ("pedido_id");
CREATE INDEX "pagos_pago_revisado_por_id_bf842120" ON "pagos_pago" ("revisado_por_id");
CREATE INDEX "pagos_pago_tienda_id_0acba72a" ON "pagos_pago" ("tienda_id");
CREATE INDEX "pago_tienda_estado_idx" ON "pagos_pago" ("tienda_id", "estado", "creado" DESC);
COMMIT;

-- ============================================================
-- promociones 0005
-- ============================================================
BEGIN;
--
-- Add field usos_por_cliente to cupon
--
ALTER TABLE "promociones_cupon" ADD COLUMN "usos_por_cliente" integer unsigned NULL CHECK ("usos_por_cliente" >= 0);
COMMIT;

-- ============================================================
-- pagos 0007
-- ============================================================
BEGIN;
--
-- Alter field costo_transferencia on liquidacion
--
-- (no-op)
--
-- Alter field monto on liquidacion
--
-- (no-op)
COMMIT;

-- ============================================================
-- pedidos 0014
-- ============================================================
BEGIN;
--
-- Add field entrega_desde to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "entrega_desde" date NULL;
--
-- Add field entrega_hasta to pedido
--
ALTER TABLE "pedidos_pedido" ADD COLUMN "entrega_hasta" date NULL;
--
-- Add field dias_entrega_max to zonaenvio
--
CREATE TABLE "new__pedidos_zonaenvio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "tarifa" decimal NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "dias_entrega_max" smallint unsigned NOT NULL CHECK ("dias_entrega_max" >= 0), CONSTRAINT "zona_tarifa_no_negativa" CHECK ("tarifa" >= '0'), CONSTRAINT "zona_nombre_unico_por_tienda" UNIQUE ("tienda_id", "nombre"));
INSERT INTO "new__pedidos_zonaenvio" ("id", "nombre", "tarifa", "activa", "orden", "tienda_id", "dias_entrega_max") SELECT "id", "nombre", "tarifa", "activa", "orden", "tienda_id", 2 FROM "pedidos_zonaenvio";
DROP TABLE "pedidos_zonaenvio";
ALTER TABLE "new__pedidos_zonaenvio" RENAME TO "pedidos_zonaenvio";
CREATE INDEX "pedidos_zonaenvio_tienda_id_f1f92876" ON "pedidos_zonaenvio" ("tienda_id");
--
-- Add field dias_entrega_min to zonaenvio
--
CREATE TABLE "new__pedidos_zonaenvio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "tarifa" decimal NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "dias_entrega_max" smallint unsigned NOT NULL CHECK ("dias_entrega_max" >= 0), "dias_entrega_min" smallint unsigned NOT NULL CHECK ("dias_entrega_min" >= 0), CONSTRAINT "zona_tarifa_no_negativa" CHECK ("tarifa" >= '0'), CONSTRAINT "zona_nombre_unico_por_tienda" UNIQUE ("tienda_id", "nombre"));
INSERT INTO "new__pedidos_zonaenvio" ("id", "nombre", "tarifa", "activa", "orden", "tienda_id", "dias_entrega_max", "dias_entrega_min") SELECT "id", "nombre", "tarifa", "activa", "orden", "tienda_id", "dias_entrega_max", 1 FROM "pedidos_zonaenvio";
DROP TABLE "pedidos_zonaenvio";
ALTER TABLE "new__pedidos_zonaenvio" RENAME TO "pedidos_zonaenvio";
CREATE INDEX "pedidos_zonaenvio_tienda_id_f1f92876" ON "pedidos_zonaenvio" ("tienda_id");
COMMIT;

-- ============================================================
-- tiendas 0014
-- ============================================================
BEGIN;
--
-- Add field dias_bajo_pedido to tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "dias_bajo_pedido" smallint unsigned NOT NULL CHECK ("dias_bajo_pedido" >= 0), "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL, "itbis_porcentaje" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL);
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", "dias_bajo_pedido") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", 7 FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";
--
-- Add field dias_para_recoger to tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL, "itbis_porcentaje" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "dias_bajo_pedido" smallint unsigned NOT NULL CHECK ("dias_bajo_pedido" >= 0), "dias_para_recoger" smallint unsigned NOT NULL CHECK ("dias_para_recoger" >= 0));
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", "dias_bajo_pedido", "dias_para_recoger") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", "dias_bajo_pedido", 1 FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";
--
-- Add field envio_gratis_desde to tienda
--
ALTER TABLE "tiendas_tienda" ADD COLUMN "envio_gratis_desde" decimal NULL;
COMMIT;

-- ============================================================
-- catalogo 0014
-- ============================================================
BEGIN;
--
-- Create model AvisoDisponible
--
CREATE TABLE "catalogo_avisodisponible" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "correo" varchar(254) NOT NULL, "creado" datetime NOT NULL, "avisado" datetime NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "aviso_disponible_unico_por_correo" UNIQUE ("producto_id", "correo"));
CREATE INDEX "catalogo_avisodisponible_producto_id_0b8fa0b8" ON "catalogo_avisodisponible" ("producto_id");
CREATE INDEX "catalogo_avisodisponible_tienda_id_e53dc59e" ON "catalogo_avisodisponible" ("tienda_id");
CREATE INDEX "catalogo_avisodisponible_usuario_id_d44fab07" ON "catalogo_avisodisponible" ("usuario_id");
CREATE INDEX "aviso_producto_pendiente_idx" ON "catalogo_avisodisponible" ("producto_id", "avisado");
COMMIT;

-- ============================================================
-- clientes 0005
-- ============================================================
BEGIN;
--
-- Add field recordatorios to perfil
--
CREATE TABLE "new__clientes_perfil" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "recordatorios" bool NOT NULL, "telefono" varchar(10) NOT NULL, "sector" varchar(80) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "usuario_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "correo_verificado" bool NOT NULL);
INSERT INTO "new__clientes_perfil" ("id", "telefono", "sector", "direccion", "referencia", "usuario_id", "correo_verificado", "recordatorios") SELECT "id", "telefono", "sector", "direccion", "referencia", "usuario_id", "correo_verificado", 1 FROM "clientes_perfil";
DROP TABLE "clientes_perfil";
ALTER TABLE "new__clientes_perfil" RENAME TO "clientes_perfil";
--
-- Create model CarritoGuardado
--
CREATE TABLE "clientes_carritoguardado" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "datos" text NOT NULL CHECK ((JSON_VALID("datos") OR "datos" IS NULL)), "actualizado" datetime NOT NULL, "recordado" datetime NULL, "usuario_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model Direccion
--
CREATE TABLE "clientes_direccion" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(40) NOT NULL, "sector" varchar(80) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "principal" bool NOT NULL, "creado" datetime NOT NULL, "usada" datetime NULL, "usuario_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "clientes_direccion_usuario_id_d32b6c60" ON "clientes_direccion" ("usuario_id");
COMMIT;

-- ============================================================
-- clientes 0007
-- ============================================================
BEGIN;
--
-- Remove field direccion from perfil
--
ALTER TABLE "clientes_perfil" DROP COLUMN "direccion";
--
-- Remove field referencia from perfil
--
ALTER TABLE "clientes_perfil" DROP COLUMN "referencia";
--
-- Remove field sector from perfil
--
ALTER TABLE "clientes_perfil" DROP COLUMN "sector";
COMMIT;

-- ============================================================
-- catalogo 0015
-- ============================================================
BEGIN;
--
-- Add field nombre_variante to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre_variante" varchar(40) NOT NULL, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "controla_stock" bool NOT NULL, "disponibilidad" varchar(15) NOT NULL, "marca" varchar(60) NOT NULL, "exento_itbis" bool NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis", "nombre_variante") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis", '' FROM "catalogo_producto";
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
CREATE INDEX "producto_disponibilidad_idx" ON "catalogo_producto" ("tienda_id", "disponibilidad");
--
-- Add field tipo_variante to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "controla_stock" bool NOT NULL, "disponibilidad" varchar(15) NOT NULL, "marca" varchar(60) NOT NULL, "exento_itbis" bool NOT NULL, "nombre_variante" varchar(40) NOT NULL, "tipo_variante" varchar(30) NOT NULL, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis", "nombre_variante", "tipo_variante") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis", "nombre_variante", '' FROM "catalogo_producto";
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
CREATE INDEX "producto_disponibilidad_idx" ON "catalogo_producto" ("tienda_id", "disponibilidad");
--
-- Add field variante_de to producto
--
ALTER TABLE "catalogo_producto" ADD COLUMN "variante_de_id" bigint NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "catalogo_producto_variante_de_id_019b89f2" ON "catalogo_producto" ("variante_de_id");
COMMIT;

-- ============================================================
-- opiniones 0002
-- ============================================================
BEGIN;
--
-- Create model FotoResena
--
CREATE TABLE "opiniones_fotoresena" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "imagen" varchar(100) NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "resena_id" bigint NOT NULL REFERENCES "opiniones_resena" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model Pregunta
--
CREATE TABLE "opiniones_pregunta" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "texto" text NOT NULL, "respuesta" text NOT NULL, "estado" varchar(10) NOT NULL, "creado" datetime NOT NULL, "respondida_en" datetime NULL, "producto_id" bigint NOT NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "respondida_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "usuario_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "opiniones_fotoresena_resena_id_56c808ac" ON "opiniones_fotoresena" ("resena_id");
CREATE INDEX "opiniones_pregunta_producto_id_ba64241e" ON "opiniones_pregunta" ("producto_id");
CREATE INDEX "opiniones_pregunta_respondida_por_id_e5ae2ce4" ON "opiniones_pregunta" ("respondida_por_id");
CREATE INDEX "opiniones_pregunta_tienda_id_5a2dc8b4" ON "opiniones_pregunta" ("tienda_id");
CREATE INDEX "opiniones_pregunta_usuario_id_a343cc70" ON "opiniones_pregunta" ("usuario_id");
CREATE INDEX "pregunta_producto_estado_idx" ON "opiniones_pregunta" ("producto_id", "estado", "creado" DESC);
COMMIT;

-- ============================================================
-- pedidos 0015
-- ============================================================
BEGIN;
--
-- Add field avisos_whatsapp to pedido
--
CREATE TABLE "new__pedidos_pedido" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "avisos_whatsapp" bool NOT NULL, "numero" varchar(20) NOT NULL UNIQUE, "token" char(32) NOT NULL UNIQUE, "nombre" varchar(120) NOT NULL, "telefono" varchar(10) NOT NULL, "correo" varchar(254) NOT NULL, "metodo_entrega" varchar(10) NOT NULL, "direccion" varchar(255) NOT NULL, "referencia" varchar(255) NOT NULL, "metodo_pago" varchar(20) NOT NULL, "transferencia_realizada" bool NOT NULL, "referencia_transferencia" varchar(60) NOT NULL, "codigo_cupon" varchar(30) NOT NULL, "subtotal" decimal NOT NULL, "descuento" decimal NOT NULL, "costo_envio" decimal NOT NULL, "total" decimal NOT NULL, "estado" varchar(12) NOT NULL, "notas_cliente" text NOT NULL, "notas_internas" text NOT NULL, "creado" datetime NOT NULL, "fecha_pago" datetime NULL, "fecha_entrega" datetime NULL, "stock_descontado" bool NOT NULL, "ip" char(39) NULL, "cupon_id" bigint NULL REFERENCES "promociones_cupon" ("id") DEFERRABLE INITIALLY DEFERRED, "zona_id" bigint NULL REFERENCES "pedidos_zonaenvio" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "impuesto" decimal NOT NULL, "porcentaje_impuesto" decimal NOT NULL, "sector" varchar(80) NOT NULL, "cliente_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "numero_seguimiento" varchar(60) NOT NULL, "transportista" varchar(60) NOT NULL, "ajuste_liquidacion_id" bigint NULL REFERENCES "pagos_liquidacion" ("id") DEFERRABLE INITIALLY DEFERRED, "liquidacion_id" bigint NULL REFERENCES "pagos_liquidacion" ("id") DEFERRABLE INITIALLY DEFERRED, "monto_liquidado" decimal NULL, "cobra_el_sitio" bool NOT NULL, "entrega_desde" date NULL, "entrega_hasta" date NULL, CONSTRAINT "pedido_envio_requiere_zona" CHECK (("metodo_entrega" = 'recoger' OR "zona_id" IS NOT NULL)), CONSTRAINT "pedido_efectivo_recoger_solo_en_tienda" CHECK ((NOT ("metodo_pago" = 'efectivo_recoger') OR "metodo_entrega" = 'recoger')), CONSTRAINT "pedido_descuento_no_supera_subtotal" CHECK (("descuento" >= '0' AND "descuento" <= ("subtotal"))), CONSTRAINT "pedido_montos_no_negativos" CHECK (("subtotal" >= '0' AND "costo_envio" >= '0' AND "total" >= '0' AND "impuesto" >= '0')));
INSERT INTO "new__pedidos_pedido" ("id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista", "ajuste_liquidacion_id", "liquidacion_id", "monto_liquidado", "cobra_el_sitio", "entrega_desde", "entrega_hasta", "avisos_whatsapp") SELECT "id", "numero", "token", "nombre", "telefono", "correo", "metodo_entrega", "direccion", "referencia", "metodo_pago", "transferencia_realizada", "referencia_transferencia", "codigo_cupon", "subtotal", "descuento", "costo_envio", "total", "estado", "notas_cliente", "notas_internas", "creado", "fecha_pago", "fecha_entrega", "stock_descontado", "ip", "cupon_id", "zona_id", "tienda_id", "impuesto", "porcentaje_impuesto", "sector", "cliente_id", "numero_seguimiento", "transportista", "ajuste_liquidacion_id", "liquidacion_id", "monto_liquidado", "cobra_el_sitio", "entrega_desde", "entrega_hasta", 0 FROM "pedidos_pedido";
DROP TABLE "pedidos_pedido";
ALTER TABLE "new__pedidos_pedido" RENAME TO "pedidos_pedido";
CREATE INDEX "pedidos_pedido_cupon_id_31eaac91" ON "pedidos_pedido" ("cupon_id");
CREATE INDEX "pedidos_pedido_zona_id_1faba78e" ON "pedidos_pedido" ("zona_id");
CREATE INDEX "pedidos_pedido_tienda_id_d3d2ad56" ON "pedidos_pedido" ("tienda_id");
CREATE INDEX "pedidos_pedido_cliente_id_84f4fc73" ON "pedidos_pedido" ("cliente_id");
CREATE INDEX "pedidos_pedido_ajuste_liquidacion_id_f93a0f71" ON "pedidos_pedido" ("ajuste_liquidacion_id");
CREATE INDEX "pedidos_pedido_liquidacion_id_b6b436e1" ON "pedidos_pedido" ("liquidacion_id");
CREATE INDEX "pedido_estado_creado_idx" ON "pedidos_pedido" ("estado", "creado" DESC);
CREATE INDEX "pedido_creado_idx" ON "pedidos_pedido" ("creado" DESC);
CREATE INDEX "pedido_fecha_pago_idx" ON "pedidos_pedido" ("fecha_pago");
CREATE INDEX "pedido_telefono_idx" ON "pedidos_pedido" ("telefono");
CREATE INDEX "pedido_ip_creado_idx" ON "pedidos_pedido" ("ip", "creado" DESC);
CREATE INDEX "pedido_tienda_creado_idx" ON "pedidos_pedido" ("tienda_id", "creado" DESC);
COMMIT;

-- ============================================================
-- catalogo 0016
-- ============================================================
BEGIN;
--
-- Add field patrocinado to producto
--
CREATE TABLE "new__catalogo_producto" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "patrocinado" bool NOT NULL, "nombre" varchar(150) NOT NULL, "slug" varchar(170) NOT NULL, "sku" varchar(40) NOT NULL, "descripcion" text NOT NULL, "precio" decimal NOT NULL, "precio_oferta" decimal NULL, "oferta_inicio" datetime NULL, "oferta_fin" datetime NULL, "stock_almacen" integer unsigned NOT NULL CHECK ("stock_almacen" >= 0), "stock_reservado" integer unsigned NOT NULL CHECK ("stock_reservado" >= 0), "destacado" bool NOT NULL, "nuevo" bool NOT NULL, "activo" bool NOT NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "categoria_id" bigint NOT NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "texto_busqueda" text NOT NULL, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, "controla_stock" bool NOT NULL, "disponibilidad" varchar(15) NOT NULL, "marca" varchar(60) NOT NULL, "exento_itbis" bool NOT NULL, "nombre_variante" varchar(40) NOT NULL, "tipo_variante" varchar(30) NOT NULL, "variante_de_id" bigint NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "producto_precio_positivo" CHECK ("precio" > '0'), CONSTRAINT "producto_oferta_menor_que_precio" CHECK (("precio_oferta" IS NULL OR ("precio_oferta" > '0' AND "precio_oferta" < ("precio")))), CONSTRAINT "producto_reservado_no_supera_almacen" CHECK ("stock_reservado" <= ("stock_almacen")), CONSTRAINT "producto_sku_unico_por_tienda" UNIQUE ("tienda_id", "sku"), CONSTRAINT "producto_slug_unico_por_tienda" UNIQUE ("tienda_id", "slug"));
INSERT INTO "new__catalogo_producto" ("id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis", "nombre_variante", "tipo_variante", "variante_de_id", "patrocinado") SELECT "id", "nombre", "slug", "sku", "descripcion", "precio", "precio_oferta", "oferta_inicio", "oferta_fin", "stock_almacen", "stock_reservado", "destacado", "nuevo", "activo", "creado", "actualizado", "categoria_id", "texto_busqueda", "tienda_id", "controla_stock", "disponibilidad", "marca", "exento_itbis", "nombre_variante", "tipo_variante", "variante_de_id", 0 FROM "catalogo_producto";
DROP TABLE "catalogo_producto";
ALTER TABLE "new__catalogo_producto" RENAME TO "catalogo_producto";
CREATE INDEX "catalogo_producto_slug_178d3ecc" ON "catalogo_producto" ("slug");
CREATE INDEX "catalogo_producto_categoria_id_19eecf17" ON "catalogo_producto" ("categoria_id");
CREATE INDEX "catalogo_producto_tienda_id_cbac6c3f" ON "catalogo_producto" ("tienda_id");
CREATE INDEX "catalogo_producto_variante_de_id_019b89f2" ON "catalogo_producto" ("variante_de_id");
CREATE INDEX "producto_activo_creado_idx" ON "catalogo_producto" ("activo", "creado" DESC);
CREATE INDEX "producto_activo_destacado_idx" ON "catalogo_producto" ("activo", "destacado");
CREATE INDEX "producto_categoria_activo_idx" ON "catalogo_producto" ("categoria_id", "activo");
CREATE INDEX "producto_precio_idx" ON "catalogo_producto" ("precio");
CREATE INDEX "producto_tienda_activo_idx" ON "catalogo_producto" ("tienda_id", "activo", "creado" DESC);
CREATE INDEX "producto_disponibilidad_idx" ON "catalogo_producto" ("tienda_id", "disponibilidad");
COMMIT;

-- ============================================================
-- core 0020
-- ============================================================
BEGIN;
--
-- Add field dias_aviso_mensualidad to configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "dias_aviso_mensualidad" smallint unsigned NOT NULL CHECK ("dias_aviso_mensualidad" >= 0), "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "descripcion" varchar(220) NOT NULL, "dias_devolucion" smallint unsigned NOT NULL CHECK ("dias_devolucion" >= 0));
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", 3 FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";
--
-- Add field dias_de_gracia to configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "descripcion" varchar(220) NOT NULL, "dias_devolucion" smallint unsigned NOT NULL CHECK ("dias_devolucion" >= 0), "dias_aviso_mensualidad" smallint unsigned NOT NULL CHECK ("dias_aviso_mensualidad" >= 0), "dias_de_gracia" smallint unsigned NOT NULL CHECK ("dias_de_gracia" >= 0));
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad", "dias_de_gracia") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad", 4 FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";
COMMIT;

-- ============================================================
-- planes 0001
-- ============================================================
BEGIN;
--
-- Create model Plan
--
CREATE TABLE "planes_plan" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(40) NOT NULL UNIQUE, "descripcion" varchar(200) NOT NULL, "mensualidad" decimal NOT NULL, "pedidos_incluidos" integer unsigned NULL CHECK ("pedidos_incluidos" >= 0), "porcentaje_excedente" decimal NOT NULL, "anuncios_portada" smallint unsigned NOT NULL CHECK ("anuncios_portada" >= 0), "productos_patrocinados" smallint unsigned NOT NULL CHECK ("productos_patrocinados" >= 0), "activo" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0));
--
-- Create model Anuncio
--
CREATE TABLE "planes_anuncio" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "titulo" varchar(70) NOT NULL, "texto" varchar(140) NOT NULL, "imagen" varchar(100) NOT NULL, "activo" bool NOT NULL, "aprobado" bool NOT NULL, "revisado_el" datetime NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "vigente_desde" datetime NULL, "vigente_hasta" datetime NULL, "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "producto_id" bigint NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model Cargo
--
CREATE TABLE "planes_cargo" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "tipo" varchar(12) NOT NULL, "periodo" date NOT NULL, "concepto" varchar(160) NOT NULL, "detalle" text NOT NULL, "monto" decimal NOT NULL, "vence" date NOT NULL, "estado" varchar(12) NOT NULL, "comprobante" varchar(100) NOT NULL, "referencia" varchar(60) NOT NULL, "enviado_el" datetime NULL, "revisado_el" datetime NULL, "nota" varchar(255) NOT NULL, "avisos" text NOT NULL CHECK ((JSON_VALID("avisos") OR "avisos" IS NULL)), "creado" datetime NOT NULL, "revisado_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "cargo_monto_positivo" CHECK ("monto" > '0'));
CREATE INDEX "planes_anuncio_producto_id_93903157" ON "planes_anuncio" ("producto_id");
CREATE INDEX "planes_anuncio_tienda_id_83a09bf4" ON "planes_anuncio" ("tienda_id");
CREATE UNIQUE INDEX "un_cargo_por_tipo_y_mes" ON "planes_cargo" ("tienda_id", "tipo", "periodo") WHERE NOT ("tipo" = 'otro');
CREATE INDEX "planes_cargo_revisado_por_id_b15b34f3" ON "planes_cargo" ("revisado_por_id");
CREATE INDEX "planes_cargo_tienda_id_a904e38b" ON "planes_cargo" ("tienda_id");
CREATE INDEX "cargo_estado_vence_idx" ON "planes_cargo" ("estado", "vence");
COMMIT;

-- ============================================================
-- tiendas 0015
-- ============================================================
BEGIN;
--
-- Add field cerrada_el to tienda
--
ALTER TABLE "tiendas_tienda" ADD COLUMN "cerrada_el" datetime NULL;
--
-- Add field cerrada_por_falta_de_pago to tienda
--
CREATE TABLE "new__tiendas_tienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL UNIQUE, "slug" varchar(60) NOT NULL UNIQUE, "prefijo" varchar(5) NOT NULL UNIQUE, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "logo" varchar(100) NOT NULL, "banner_titulo" varchar(120) NOT NULL, "banner_subtitulo" varchar(220) NOT NULL, "banner_texto_boton" varchar(40) NOT NULL, "banner_imagen" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "direccion_tienda" varchar(255) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "permitir_contra_entrega" bool NOT NULL, "creada" datetime NOT NULL, "itbis_porcentaje" decimal NOT NULL, "comision_porcentaje" decimal NOT NULL, "dias_bajo_pedido" smallint unsigned NOT NULL CHECK ("dias_bajo_pedido" >= 0), "dias_para_recoger" smallint unsigned NOT NULL CHECK ("dias_para_recoger" >= 0), "envio_gratis_desde" decimal NULL, "cerrada_el" datetime NULL, "cerrada_por_falta_de_pago" bool NOT NULL);
INSERT INTO "new__tiendas_tienda" ("id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", "dias_bajo_pedido", "dias_para_recoger", "envio_gratis_desde", "cerrada_el", "cerrada_por_falta_de_pago") SELECT "id", "nombre", "slug", "prefijo", "activa", "orden", "logo", "banner_titulo", "banner_subtitulo", "banner_texto_boton", "banner_imagen", "correo", "telefono", "horario", "whatsapp", "direccion_tienda", "facebook", "instagram", "tiktok", "permitir_contra_entrega", "creada", "itbis_porcentaje", "comision_porcentaje", "dias_bajo_pedido", "dias_para_recoger", "envio_gratis_desde", "cerrada_el", 0 FROM "tiendas_tienda";
DROP TABLE "tiendas_tienda";
ALTER TABLE "new__tiendas_tienda" RENAME TO "tiendas_tienda";
--
-- Add field habilitada_el to tienda
--
ALTER TABLE "tiendas_tienda" ADD COLUMN "habilitada_el" datetime NULL;
--
-- Add field plan to tienda
--
ALTER TABLE "tiendas_tienda" ADD COLUMN "plan_id" bigint NULL REFERENCES "planes_plan" ("id") DEFERRABLE INITIALLY DEFERRED;
--
-- Add field plan_desde to tienda
--
ALTER TABLE "tiendas_tienda" ADD COLUMN "plan_desde" date NULL;
--
-- Alter field comision_porcentaje on tienda
--
-- (no-op)
--
-- Create model CuentaBancaria
--
CREATE TABLE "tiendas_cuentabancaria" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "banco" varchar(80) NOT NULL, "tipo_cuenta" varchar(10) NOT NULL, "numero" varchar(30) NOT NULL, "titular" varchar(120) NOT NULL, "cedula_rnc" varchar(20) NOT NULL, "activa" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "cuenta_bancaria_unica_por_tienda" UNIQUE ("tienda_id", "banco", "numero"));
CREATE INDEX "tiendas_tienda_plan_id_82c64cbc" ON "tiendas_tienda" ("plan_id");
CREATE INDEX "tiendas_cuentabancaria_tienda_id_921c2131" ON "tiendas_cuentabancaria" ("tienda_id");
COMMIT;

-- ============================================================
-- core 0021
-- ============================================================
BEGIN;
--
-- Add field video_megas_maximos to configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "video_megas_maximos" smallint unsigned NOT NULL CHECK ("video_megas_maximos" >= 0), "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "descripcion" varchar(220) NOT NULL, "dias_devolucion" smallint unsigned NOT NULL CHECK ("dias_devolucion" >= 0), "dias_aviso_mensualidad" smallint unsigned NOT NULL CHECK ("dias_aviso_mensualidad" >= 0), "dias_de_gracia" smallint unsigned NOT NULL CHECK ("dias_de_gracia" >= 0));
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad", "dias_de_gracia", "video_megas_maximos") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad", "dias_de_gracia", 10 FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";
--
-- Add field video_segundos_maximos to configuraciontienda
--
CREATE TABLE "new__core_configuraciontienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre" varchar(80) NOT NULL, "logo" varchar(100) NOT NULL, "correo" varchar(254) NOT NULL, "telefono" varchar(20) NOT NULL, "horario" varchar(150) NOT NULL, "whatsapp" varchar(20) NOT NULL, "facebook" varchar(200) NOT NULL, "instagram" varchar(200) NOT NULL, "tiktok" varchar(200) NOT NULL, "dias_producto_nuevo" smallint unsigned NOT NULL CHECK ("dias_producto_nuevo" >= 0), "umbral_stock_bajo" smallint unsigned NOT NULL CHECK ("umbral_stock_bajo" >= 0), "horas_vencimiento_pedido" smallint unsigned NOT NULL CHECK ("horas_vencimiento_pedido" >= 0), "mostrar_cantidad_exacta" bool NOT NULL, "descripcion" varchar(220) NOT NULL, "dias_devolucion" smallint unsigned NOT NULL CHECK ("dias_devolucion" >= 0), "dias_aviso_mensualidad" smallint unsigned NOT NULL CHECK ("dias_aviso_mensualidad" >= 0), "dias_de_gracia" smallint unsigned NOT NULL CHECK ("dias_de_gracia" >= 0), "video_megas_maximos" smallint unsigned NOT NULL CHECK ("video_megas_maximos" >= 0), "video_segundos_maximos" smallint unsigned NOT NULL CHECK ("video_segundos_maximos" >= 0));
INSERT INTO "new__core_configuraciontienda" ("id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad", "dias_de_gracia", "video_megas_maximos", "video_segundos_maximos") SELECT "id", "nombre", "logo", "correo", "telefono", "horario", "whatsapp", "facebook", "instagram", "tiktok", "dias_producto_nuevo", "umbral_stock_bajo", "horas_vencimiento_pedido", "mostrar_cantidad_exacta", "descripcion", "dias_devolucion", "dias_aviso_mensualidad", "dias_de_gracia", "video_megas_maximos", 15 FROM "core_configuraciontienda";
DROP TABLE "core_configuraciontienda";
ALTER TABLE "new__core_configuraciontienda" RENAME TO "core_configuraciontienda";
COMMIT;

-- ============================================================
-- planes 0003
-- ============================================================
BEGIN;
--
-- Add field videos_portada to plan
--
CREATE TABLE "new__planes_plan" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "videos_portada" smallint unsigned NOT NULL CHECK ("videos_portada" >= 0), "nombre" varchar(40) NOT NULL UNIQUE, "descripcion" varchar(200) NOT NULL, "mensualidad" decimal NOT NULL, "pedidos_incluidos" integer unsigned NULL CHECK ("pedidos_incluidos" >= 0), "porcentaje_excedente" decimal NOT NULL, "anuncios_portada" smallint unsigned NOT NULL CHECK ("anuncios_portada" >= 0), "productos_patrocinados" smallint unsigned NOT NULL CHECK ("productos_patrocinados" >= 0), "activo" bool NOT NULL, "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0));
INSERT INTO "new__planes_plan" ("id", "nombre", "descripcion", "mensualidad", "pedidos_incluidos", "porcentaje_excedente", "anuncios_portada", "productos_patrocinados", "activo", "orden", "videos_portada") SELECT "id", "nombre", "descripcion", "mensualidad", "pedidos_incluidos", "porcentaje_excedente", "anuncios_portada", "productos_patrocinados", "activo", "orden", 0 FROM "planes_plan";
DROP TABLE "planes_plan";
ALTER TABLE "new__planes_plan" RENAME TO "planes_plan";
--
-- Create model Video
--
CREATE TABLE "planes_video" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "titulo" varchar(80) NOT NULL, "archivo" varchar(120) NOT NULL, "activo" bool NOT NULL, "aprobado" bool NOT NULL, "revisado_el" datetime NULL, "duracion" decimal NOT NULL, "peso" integer unsigned NOT NULL CHECK ("peso" >= 0), "vistas" integer unsigned NOT NULL CHECK ("vistas" >= 0), "orden" smallint unsigned NOT NULL CHECK ("orden" >= 0), "creado" datetime NOT NULL, "actualizado" datetime NOT NULL, "producto_id" bigint NULL REFERENCES "catalogo_producto" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NOT NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "planes_video_producto_id_6e6430f9" ON "planes_video" ("producto_id");
CREATE INDEX "planes_video_tienda_id_575bd47d" ON "planes_video" ("tienda_id");
COMMIT;

-- ============================================================
-- tiendas 0017
-- ============================================================
BEGIN;
--
-- Create model SolicitudTienda
--
CREATE TABLE "tiendas_solicitudtienda" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "nombre_responsable" varchar(120) NOT NULL, "nombre_comercial" varchar(80) NOT NULL, "correo" varchar(150) NOT NULL, "telefono" varchar(10) NOT NULL, "descripcion" text NOT NULL, "redes" varchar(200) NOT NULL, "estado" varchar(12) NOT NULL, "notas" text NOT NULL, "revisada_el" datetime NULL, "creada" datetime NOT NULL, "actualizada" datetime NOT NULL, "categoria_id" bigint NULL REFERENCES "catalogo_categoria" ("id") DEFERRABLE INITIALLY DEFERRED, "revisada_por_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "tienda_id" bigint NULL REFERENCES "tiendas_tienda" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "tiendas_solicitudtienda_categoria_id_6ccc58ee" ON "tiendas_solicitudtienda" ("categoria_id");
CREATE INDEX "tiendas_solicitudtienda_revisada_por_id_2f13825d" ON "tiendas_solicitudtienda" ("revisada_por_id");
CREATE INDEX "tiendas_solicitudtienda_tienda_id_00fa117b" ON "tiendas_solicitudtienda" ("tienda_id");
CREATE INDEX "solicitud_estado_idx" ON "tiendas_solicitudtienda" ("estado", "creada" DESC);
COMMIT;
