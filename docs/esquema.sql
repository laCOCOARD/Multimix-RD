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
