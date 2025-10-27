-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.CentrosTrabajo (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nombre text NOT NULL,
  unidad_capacidad text DEFAULT 'MINUTOS'::text CHECK (unidad_capacidad = ANY (ARRAY['MINUTOS'::text, 'HORAS'::text])),
  tiempo_disponible_std_dia numeric DEFAULT 480 CHECK (tiempo_disponible_std_dia >= 0::numeric),
  eficiencia numeric DEFAULT 1.0 CHECK (eficiencia >= 0::numeric AND eficiencia <= 1::numeric),
  utilizacion numeric DEFAULT 1.0 CHECK (utilizacion >= 0::numeric AND utilizacion <= 1::numeric),
  numero_maquinas integer DEFAULT 1 CHECK (numero_maquinas > 0),
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  updated_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT CentrosTrabajo_pkey PRIMARY KEY (id)
);
CREATE TABLE public.clientes (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL UNIQUE,
  codigo character varying NOT NULL UNIQUE,
  nombre character varying NOT NULL,
  telefono character varying,
  email character varying UNIQUE,
  cuit character varying NOT NULL UNIQUE,
  activo boolean DEFAULT true,
  updated_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  direccion_id integer,
  condicion_iva character varying,
  condicion_venta integer DEFAULT 1,
  estado integer,
  contrasena character varying,
  razon_social character varying,
  estado_aprobacion character varying,
  CONSTRAINT clientes_pkey PRIMARY KEY (id),
  CONSTRAINT clientes_direccion_id_fkey FOREIGN KEY (direccion_id) REFERENCES public.usuario_direccion(id)
);
CREATE TABLE public.configuracion (
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone,
  valor text,
  clave text NOT NULL,
  CONSTRAINT configuracion_pkey PRIMARY KEY (clave)
);
CREATE TABLE public.despachos (
  id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
  id_pedido integer NOT NULL,
  nombre_transportista character varying NOT NULL,
  dni_transportista character varying NOT NULL,
  patente_vehiculo character varying,
  telefono_transportista character varying,
  observaciones text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT despachos_pkey PRIMARY KEY (id),
  CONSTRAINT despachos_id_pedido_fkey FOREIGN KEY (id_pedido) REFERENCES public.pedidos(id)
);
CREATE TABLE public.historial_precios_insumos (
  id integer NOT NULL DEFAULT nextval('historial_precios_insumos_id_seq'::regclass),
  id_insumo uuid NOT NULL,
  precio_anterior numeric NOT NULL,
  precio_nuevo numeric NOT NULL,
  fecha_cambio timestamp with time zone NOT NULL DEFAULT now(),
  usuario_cambio character varying,
  origen_cambio character varying,
  archivo_origen character varying,
  observaciones text,
  CONSTRAINT historial_precios_insumos_pkey PRIMARY KEY (id),
  CONSTRAINT historial_precios_insumos_id_insumo_fkey FOREIGN KEY (id_insumo) REFERENCES public.insumos_catalogo(id_insumo)
);
CREATE TABLE public.insumos_catalogo (
  id_insumo uuid NOT NULL DEFAULT gen_random_uuid(),
  nombre character varying NOT NULL,
  codigo_interno character varying UNIQUE,
  codigo_ean character varying,
  unidad_medida character varying NOT NULL,
  categoria character varying,
  descripcion text,
  tem_recomendada numeric,
  stock_min integer DEFAULT 0 CHECK (stock_min >= 0),
  stock_max integer,
  vida_util_dias integer CHECK (vida_util_dias IS NULL OR vida_util_dias > 0),
  es_critico boolean DEFAULT false,
  requiere_certificacion boolean DEFAULT false,
  activo boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  precio_unitario numeric NOT NULL DEFAULT '1'::numeric,
  stock_actual real,
  id_proveedor integer,
  tiempo_entrega_dias integer NOT NULL DEFAULT 1,
  CONSTRAINT insumos_catalogo_pkey PRIMARY KEY (id_insumo),
  CONSTRAINT insumos_catalogo_id_proveedor_fkey FOREIGN KEY (id_proveedor) REFERENCES public.proveedores(id)
);
CREATE TABLE public.insumos_inventario (
  id_lote uuid NOT NULL DEFAULT gen_random_uuid(),
  id_insumo uuid NOT NULL,
  numero_lote_proveedor character varying,
  cantidad_inicial numeric NOT NULL,
  cantidad_actual numeric NOT NULL,
  precio_unitario numeric CHECK (precio_unitario IS NULL OR precio_unitario >= 0::numeric),
  costo_total numeric DEFAULT (cantidad_inicial * precio_unitario),
  f_ingreso date NOT NULL DEFAULT CURRENT_DATE,
  f_vencimiento date,
  ubicacion_fisica character varying,
  documento_ingreso character varying,
  observaciones text,
  estado character varying DEFAULT 'disponible'::character varying CHECK (estado::text = ANY (ARRAY['disponible'::character varying, 'reservado'::character varying, 'agotado'::character varying, 'vencido'::character varying]::text[])),
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  usuario_ingreso_id integer,
  id_proveedor integer,
  CONSTRAINT insumos_inventario_pkey PRIMARY KEY (id_lote),
  CONSTRAINT insumos_inventario_id_insumo_fkey FOREIGN KEY (id_insumo) REFERENCES public.insumos_catalogo(id_insumo),
  CONSTRAINT fk_usuario_ingreso FOREIGN KEY (usuario_ingreso_id) REFERENCES public.usuarios(id),
  CONSTRAINT fk_preveedor_ingreso FOREIGN KEY (id_proveedor) REFERENCES public.proveedores(id)
);
CREATE TABLE public.lotes_productos (
  id_lote integer NOT NULL DEFAULT nextval('lotes_productos_id_lote_seq'::regclass) UNIQUE,
  producto_id integer NOT NULL,
  numero_lote character varying NOT NULL UNIQUE,
  cantidad_inicial numeric NOT NULL,
  cantidad_actual numeric NOT NULL,
  fecha_produccion date NOT NULL DEFAULT CURRENT_DATE,
  fecha_vencimiento date,
  costo_produccion_unitario numeric,
  estado character varying NOT NULL DEFAULT 'DISPONIBLE'::character varying CHECK (estado::text = ANY (ARRAY['DISPONIBLE'::character varying, 'RESERVADO'::character varying, 'AGOTADO'::character varying, 'VENCIDO'::character varying, 'RETIRADO'::character varying]::text[])),
  ubicacion_fisica character varying,
  orden_produccion_id integer,
  observaciones text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT lotes_productos_pkey PRIMARY KEY (id_lote, producto_id),
  CONSTRAINT lotes_productos_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES public.productos(id)
);
CREATE TABLE public.notificaciones (
  id integer NOT NULL DEFAULT nextval('notificaciones_id_seq'::regclass),
  usuario_id integer NOT NULL,
  mensaje text NOT NULL,
  tipo character varying DEFAULT 'INFO'::character varying,
  leida boolean NOT NULL DEFAULT false,
  url_destino character varying,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT notificaciones_pkey PRIMARY KEY (id),
  CONSTRAINT notificaciones_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id)
);
CREATE TABLE public.operacionesreceta (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  receta_id bigint NOT NULL,
  secuencia integer NOT NULL CHECK (secuencia > 0),
  nombre_operacion text NOT NULL,
  tiempo_preparacion numeric DEFAULT 0 CHECK (tiempo_preparacion >= 0::numeric),
  tiempo_ejecucion_unitario numeric DEFAULT 0 CHECK (tiempo_ejecucion_unitario >= 0::numeric),
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  updated_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT operacionesreceta_pkey PRIMARY KEY (id),
  CONSTRAINT operacionesreceta_receta_id_fkey FOREIGN KEY (receta_id) REFERENCES public.recetas(id)
);
CREATE TABLE public.orden_compra_items (
  id integer NOT NULL DEFAULT nextval('orden_compra_items_id_seq'::regclass),
  orden_compra_id integer,
  insumo_id uuid,
  cantidad_solicitada numeric NOT NULL,
  cantidad_recibida numeric DEFAULT 0,
  precio_unitario numeric NOT NULL,
  subtotal numeric DEFAULT (cantidad_solicitada * precio_unitario),
  estado character varying DEFAULT 'PENDIENTE'::character varying,
  observaciones text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT orden_compra_items_pkey PRIMARY KEY (id),
  CONSTRAINT orden_compra_items_orden_compra_id_fkey FOREIGN KEY (orden_compra_id) REFERENCES public.ordenes_compra(id),
  CONSTRAINT orden_compra_items_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES public.insumos_catalogo(id_insumo)
);
CREATE TABLE public.ordenes_compra (
  id integer NOT NULL DEFAULT nextval('ordenes_compra_id_seq'::regclass),
  codigo_oc character varying NOT NULL UNIQUE,
  proveedor_id integer,
  pedido_id integer,
  orden_produccion_id integer,
  estado character varying DEFAULT 'PENDIENTE'::character varying,
  fecha_emision date DEFAULT CURRENT_DATE,
  fecha_estimada_entrega date,
  fecha_real_entrega date,
  prioridad character varying DEFAULT 'NORMAL'::character varying,
  subtotal numeric DEFAULT 0,
  iva numeric DEFAULT 0,
  total numeric DEFAULT 0,
  observaciones text,
  usuario_creador_id integer,
  usuario_aprobador_id integer,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  fecha_creacion timestamp with time zone DEFAULT now(),
  complementa_a_orden_id integer,
  CONSTRAINT ordenes_compra_pkey PRIMARY KEY (id),
  CONSTRAINT ordenes_compra_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores(id),
  CONSTRAINT ordenes_compra_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id),
  CONSTRAINT ordenes_compra_usuario_creador_id_fkey FOREIGN KEY (usuario_creador_id) REFERENCES public.usuarios(id),
  CONSTRAINT ordenes_compra_usuario_aprobador_id_fkey FOREIGN KEY (usuario_aprobador_id) REFERENCES public.usuarios(id),
  CONSTRAINT ordenes_compra_orden_produccion_id_fkey FOREIGN KEY (orden_produccion_id) REFERENCES public.ordenes_produccion(id)
);
CREATE TABLE public.ordenes_produccion (
  id integer NOT NULL DEFAULT nextval('ordenes_produccion_id_seq'::regclass),
  codigo character varying NOT NULL UNIQUE,
  producto_id integer NOT NULL,
  receta_id integer NOT NULL,
  cantidad_planificada numeric NOT NULL,
  estado character varying NOT NULL DEFAULT 'PLANIFICADA'::character varying CHECK (estado::text = ANY (ARRAY['PENDIENTE'::character varying::text, 'APROBADA'::character varying::text, 'EN_PROCESO'::character varying::text, 'COMPLETADA'::character varying::text, 'CANCELADA'::character varying::text, 'EN ESPERA'::character varying::text, 'LISTA PARA PRODUCIR'::character varying::text, 'EN_LINEA_1'::character varying::text, 'EN_LINEA_2'::character varying::text, 'EN_EMPAQUETADO'::character varying::text, 'CONTROL_DE_CALIDAD'::character varying::text, 'CONSOLIDADA'::character varying::text])),
  fecha_planificada date,
  fecha_inicio timestamp with time zone,
  fecha_fin timestamp with time zone,
  usuario_creador_id integer,
  observaciones text,
  prioridad character varying DEFAULT 'NORMAL'::character varying,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  fecha_fin_estimada timestamp with time zone,
  fecha_aprobacion timestamp with time zone,
  supervisor_responsable_id integer,
  linea_produccion integer,
  super_op_id integer,
  fecha_meta date,
  linea_asignada smallint,
  operario_asignado_id integer,
  sugerencia_fecha_inicio date,
  sugerencia_plazo_total_dias integer,
  sugerencia_t_produccion_dias integer,
  sugerencia_t_aprovisionamiento_dias integer,
  sugerencia_linea integer,
  fecha_inicio_planificada date,
  orden_compra_id integer,
  CONSTRAINT ordenes_produccion_pkey PRIMARY KEY (id),
  CONSTRAINT ordenes_produccion_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES public.productos(id),
  CONSTRAINT ordenes_produccion_receta_id_fkey FOREIGN KEY (receta_id) REFERENCES public.recetas(id),
  CONSTRAINT ordenes_produccion_usuario_creador_id_fkey FOREIGN KEY (usuario_creador_id) REFERENCES public.usuarios(id),
  CONSTRAINT ordenes_produccion_supervisor_responsable_id_fkey FOREIGN KEY (supervisor_responsable_id) REFERENCES public.usuarios(id),
  CONSTRAINT ordenes_produccion_super_op_id_fkey FOREIGN KEY (super_op_id) REFERENCES public.ordenes_produccion(id),
  CONSTRAINT ordenes_produccion_operario_asignado_id_fkey FOREIGN KEY (operario_asignado_id) REFERENCES public.usuarios(id),
  CONSTRAINT ordenes_produccion_orden_compra_id_fkey FOREIGN KEY (orden_compra_id) REFERENCES public.ordenes_compra(id)
);
CREATE TABLE public.pedido_items (
  id integer NOT NULL DEFAULT nextval('pedido_items_id_seq'::regclass),
  pedido_id integer NOT NULL,
  producto_id integer NOT NULL,
  cantidad integer NOT NULL,
  estado character varying NOT NULL DEFAULT 'PENDIENTE'::character varying,
  orden_produccion_id integer,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT pedido_items_pkey PRIMARY KEY (id),
  CONSTRAINT pedido_items_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id),
  CONSTRAINT pedido_items_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES public.productos(id),
  CONSTRAINT pedido_items_orden_produccion_id_fkey FOREIGN KEY (orden_produccion_id) REFERENCES public.ordenes_produccion(id)
);
CREATE TABLE public.pedidos (
  id integer NOT NULL DEFAULT nextval('pedidos_id_seq'::regclass),
  nombre_cliente character varying NOT NULL,
  fecha_solicitud date NOT NULL,
  estado character varying NOT NULL DEFAULT 'PENDIENTE'::character varying,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  fecha_requerido date,
  precio_orden real,
  id_cliente integer,
  id_direccion_entrega integer,
  comentarios_adicionales text,
  fecha_estimativa_proceso date,
  condicion_venta character varying,
  CONSTRAINT pedidos_pkey PRIMARY KEY (id),
  CONSTRAINT pedidos_id_cliente_fkey FOREIGN KEY (id_cliente) REFERENCES public.clientes(id),
  CONSTRAINT pedidos_id_direccion_entrega_fkey FOREIGN KEY (id_direccion_entrega) REFERENCES public.usuario_direccion(id)
);
CREATE TABLE public.productos (
  id integer NOT NULL DEFAULT nextval('productos_id_seq'::regclass),
  codigo character varying NOT NULL UNIQUE,
  nombre character varying NOT NULL,
  descripcion text,
  categoria character varying NOT NULL,
  activo boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  unidad_medida character varying,
  precio_unitario numeric DEFAULT '1'::numeric,
  porcentaje_extra numeric DEFAULT '0'::numeric,
  iva boolean DEFAULT true,
  descuento boolean,
  descuento_porcentual smallint,
  unidades_por_paquete integer DEFAULT 1,
  peso_por_paquete_unidad character varying,
  peso_por_paquete_valor real DEFAULT '0'::real,
  stock_min_produccion integer,
  cantidad_maxima_x_pedido numeric,
  CONSTRAINT productos_pkey PRIMARY KEY (id)
);
CREATE TABLE public.proveedores (
  id integer NOT NULL DEFAULT nextval('proveedores_id_seq'::regclass),
  codigo character varying NOT NULL UNIQUE,
  nombre character varying NOT NULL,
  contacto character varying,
  telefono character varying,
  email character varying,
  direccion text,
  cuit character varying,
  condicion_iva character varying,
  activo boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  direccion_id integer,
  CONSTRAINT proveedores_pkey PRIMARY KEY (id),
  CONSTRAINT proveedores_direccion_id_fkey FOREIGN KEY (direccion_id) REFERENCES public.usuario_direccion(id)
);
CREATE TABLE public.recepcion_items (
  id integer NOT NULL DEFAULT nextval('recepcion_items_id_seq'::regclass),
  recepcion_id integer,
  orden_compra_item_id integer,
  insumo_id uuid,
  cantidad_recibida numeric NOT NULL,
  lote_numero character varying,
  fecha_vencimiento date,
  calidad character varying DEFAULT 'BUENA'::character varying,
  observaciones text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT recepcion_items_pkey PRIMARY KEY (id),
  CONSTRAINT recepcion_items_recepcion_id_fkey FOREIGN KEY (recepcion_id) REFERENCES public.recepciones_compra(id),
  CONSTRAINT recepcion_items_orden_compra_item_id_fkey FOREIGN KEY (orden_compra_item_id) REFERENCES public.orden_compra_items(id),
  CONSTRAINT recepcion_items_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES public.insumos_catalogo(id_insumo)
);
CREATE TABLE public.recepciones_compra (
  id integer NOT NULL DEFAULT nextval('recepciones_compra_id_seq'::regclass),
  orden_compra_id integer,
  codigo_recepcion character varying NOT NULL UNIQUE,
  fecha_recepcion date DEFAULT CURRENT_DATE,
  usuario_receptor_id integer,
  proveedor_id integer,
  estado character varying DEFAULT 'BORRADOR'::character varying,
  observaciones text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT recepciones_compra_pkey PRIMARY KEY (id),
  CONSTRAINT recepciones_compra_orden_compra_id_fkey FOREIGN KEY (orden_compra_id) REFERENCES public.ordenes_compra(id),
  CONSTRAINT recepciones_compra_usuario_receptor_id_fkey FOREIGN KEY (usuario_receptor_id) REFERENCES public.usuarios(id),
  CONSTRAINT recepciones_compra_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores(id)
);
CREATE TABLE public.receta_ingredientes (
  id integer NOT NULL DEFAULT nextval('receta_ingredientes_id_seq'::regclass),
  receta_id integer NOT NULL,
  id_insumo uuid NOT NULL,
  cantidad numeric NOT NULL,
  unidad_medida character varying NOT NULL,
  CONSTRAINT receta_ingredientes_pkey PRIMARY KEY (id),
  CONSTRAINT receta_ingredientes_receta_id_fkey FOREIGN KEY (receta_id) REFERENCES public.recetas(id),
  CONSTRAINT receta_ingredientes_id_insumo_fkey FOREIGN KEY (id_insumo) REFERENCES public.insumos_catalogo(id_insumo)
);
CREATE TABLE public.recetas (
  id integer NOT NULL DEFAULT nextval('recetas_id_seq'::regclass),
  nombre character varying NOT NULL,
  producto_id integer NOT NULL,
  version character varying NOT NULL,
  descripcion text,
  rendimiento numeric,
  activa boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  tiempo_preparacion_minutos integer NOT NULL DEFAULT 0,
  linea_compatible text NOT NULL DEFAULT '2'::text,
  tiempo_prod_unidad_linea1 numeric DEFAULT 0,
  tiempo_prod_unidad_linea2 numeric DEFAULT 0,
  CONSTRAINT recetas_pkey PRIMARY KEY (id),
  CONSTRAINT recetas_producto_id_fkey FOREIGN KEY (producto_id) REFERENCES public.productos(id)
);
CREATE TABLE public.registros_acceso (
  id integer NOT NULL DEFAULT nextval('registros_acceso_id_seq'::regclass),
  usuario_id integer,
  fecha_hora timestamp without time zone DEFAULT now(),
  tipo character varying NOT NULL,
  metodo character varying NOT NULL,
  dispositivo character varying NOT NULL,
  observaciones text,
  sesion_totem_id integer,
  ubicacion_totem character varying,
  CONSTRAINT registros_acceso_pkey PRIMARY KEY (id),
  CONSTRAINT registros_acceso_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id),
  CONSTRAINT registros_acceso_sesion_totem_id_fkey FOREIGN KEY (sesion_totem_id) REFERENCES public.totem_sesiones(id)
);
CREATE TABLE public.reservas_insumos (
  id integer NOT NULL DEFAULT nextval('reservas_insumos_id_seq'::regclass),
  orden_produccion_id integer NOT NULL,
  lote_inventario_id uuid NOT NULL,
  insumo_id uuid NOT NULL,
  cantidad_reservada numeric NOT NULL,
  estado character varying NOT NULL DEFAULT 'RESERVADO'::character varying,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  usuario_reserva_id integer,
  CONSTRAINT reservas_insumos_pkey PRIMARY KEY (id),
  CONSTRAINT reservas_insumos_insumo_id_fkey FOREIGN KEY (insumo_id) REFERENCES public.insumos_catalogo(id_insumo),
  CONSTRAINT reservas_insumos_usuario_reserva_id_fkey FOREIGN KEY (usuario_reserva_id) REFERENCES public.usuarios(id),
  CONSTRAINT reservas_insumos_orden_produccion_id_fkey FOREIGN KEY (orden_produccion_id) REFERENCES public.ordenes_produccion(id),
  CONSTRAINT reservas_insumos_lote_inventario_id_fkey FOREIGN KEY (lote_inventario_id) REFERENCES public.insumos_inventario(id_lote)
);
CREATE TABLE public.reservas_productos (
  id integer NOT NULL DEFAULT nextval('reservas_productos_id_seq'::regclass),
  lote_producto_id integer NOT NULL,
  pedido_id integer NOT NULL,
  pedido_item_id integer NOT NULL,
  cantidad_reservada numeric NOT NULL,
  cantidad_despachada numeric DEFAULT 0,
  estado character varying NOT NULL DEFAULT 'RESERVADO'::character varying CHECK (estado::text = ANY (ARRAY['RESERVADO'::character varying, 'PARCIAL'::character varying, 'COMPLETADO'::character varying, 'CANCELADO'::character varying]::text[])),
  fecha_reserva timestamp with time zone DEFAULT now(),
  fecha_despacho timestamp with time zone,
  usuario_reserva_id integer,
  CONSTRAINT reservas_productos_pkey PRIMARY KEY (id, lote_producto_id, pedido_id, pedido_item_id),
  CONSTRAINT reservas_productos_lote_producto_id_fkey FOREIGN KEY (lote_producto_id) REFERENCES public.lotes_productos(id_lote),
  CONSTRAINT reservas_productos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id),
  CONSTRAINT reservas_productos_pedido_item_id_fkey FOREIGN KEY (pedido_item_id) REFERENCES public.pedido_items(id)
);
CREATE TABLE public.roles (
  id integer NOT NULL DEFAULT nextval('roles_id_seq'::regclass),
  codigo character varying NOT NULL UNIQUE,
  nombre character varying NOT NULL,
  nivel integer NOT NULL DEFAULT 1,
  descripcion text,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT roles_pkey PRIMARY KEY (id)
);
CREATE TABLE public.sectores (
  id integer NOT NULL DEFAULT nextval('sectores_id_seq'::regclass),
  codigo character varying NOT NULL UNIQUE,
  nombre character varying NOT NULL,
  descripcion text,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT sectores_pkey PRIMARY KEY (id)
);
CREATE TABLE public.token_blacklist (
  jti character varying NOT NULL,
  exp timestamp with time zone NOT NULL,
  CONSTRAINT token_blacklist_pkey PRIMARY KEY (jti)
);
CREATE TABLE public.totem_sesiones (
  id integer NOT NULL DEFAULT nextval('totem_sesiones_id_seq'::regclass),
  usuario_id integer NOT NULL,
  fecha_inicio timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  fecha_fin timestamp without time zone,
  session_id character varying NOT NULL,
  metodo_acceso character varying NOT NULL CHECK (metodo_acceso::text = ANY (ARRAY['FACIAL'::character varying, 'CREDENCIAL'::character varying]::text[])),
  dispositivo_totem character varying NOT NULL,
  activa boolean DEFAULT true,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT totem_sesiones_pkey PRIMARY KEY (id),
  CONSTRAINT totem_sesiones_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id)
);
CREATE TABLE public.u_autorizaciones_ingreso (
  id integer NOT NULL DEFAULT nextval('autorizaciones_ingreso_id_seq'::regclass),
  usuario_id integer NOT NULL,
  supervisor_id integer NOT NULL,
  fecha_autorizada date NOT NULL,
  turno_autorizado_id integer NOT NULL,
  motivo text,
  created_at timestamp with time zone DEFAULT (now() AT TIME ZONE 'utc'::text),
  tipo character varying NOT NULL DEFAULT ''::character varying,
  estado character varying NOT NULL DEFAULT 'PENDIENTE'::character varying,
  comentario_supervisor text,
  CONSTRAINT u_autorizaciones_ingreso_pkey PRIMARY KEY (id),
  CONSTRAINT fk_usuario_autorizado FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id),
  CONSTRAINT fk_supervisor FOREIGN KEY (supervisor_id) REFERENCES public.usuarios(id),
  CONSTRAINT fk_turno_autorizado FOREIGN KEY (turno_autorizado_id) REFERENCES public.usuarios_turnos(id)
);
CREATE TABLE public.u_autorizaciones_notificaciones (
  id integer NOT NULL DEFAULT nextval('autorizaciones_notificaciones_id_seq'::regclass),
  usuario_id integer NOT NULL,
  tipo character varying NOT NULL,
  mensaje text NOT NULL,
  leida boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT u_autorizaciones_notificaciones_pkey PRIMARY KEY (id),
  CONSTRAINT fk_usuario_notificacion FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id)
);
CREATE TABLE public.usuario_direccion (
  id integer NOT NULL DEFAULT nextval('usuario_direccion_id_seq'::regclass),
  calle character varying NOT NULL,
  altura integer NOT NULL,
  piso character varying,
  depto character varying,
  codigo_postal character varying,
  localidad character varying NOT NULL,
  provincia character varying NOT NULL,
  latitud numeric,
  longitud numeric,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT usuario_direccion_pkey PRIMARY KEY (id)
);
CREATE TABLE public.usuario_permisos (
  id integer NOT NULL DEFAULT nextval('permisos_id_seq'::regclass),
  role_id integer NOT NULL,
  sector_id integer NOT NULL,
  accion character varying NOT NULL,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT usuario_permisos_pkey PRIMARY KEY (id),
  CONSTRAINT fk_role FOREIGN KEY (role_id) REFERENCES public.roles(id),
  CONSTRAINT fk_sector FOREIGN KEY (sector_id) REFERENCES public.sectores(id)
);
CREATE TABLE public.usuario_sectores (
  id integer NOT NULL DEFAULT nextval('usuario_sectores_id_seq'::regclass),
  usuario_id integer NOT NULL,
  sector_id integer NOT NULL,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT usuario_sectores_pkey PRIMARY KEY (id),
  CONSTRAINT usuario_sectores_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id),
  CONSTRAINT usuario_sectores_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectores(id)
);
CREATE TABLE public.usuarios (
  id integer NOT NULL DEFAULT nextval('usuarios_id_seq'::regclass),
  email character varying NOT NULL UNIQUE,
  password_hash character varying NOT NULL,
  nombre character varying NOT NULL,
  apellido character varying NOT NULL,
  activo boolean DEFAULT true,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  legajo character varying NOT NULL UNIQUE,
  cuil_cuit character varying UNIQUE,
  telefono character varying,
  fecha_nacimiento date,
  fecha_ingreso date,
  facial_encoding text,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  ultimo_login_web timestamp with time zone,
  role_id integer NOT NULL,
  direccion_id integer,
  turno_id integer,
  CONSTRAINT usuarios_pkey PRIMARY KEY (id),
  CONSTRAINT usuarios_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id),
  CONSTRAINT fk_usuarios_direcciones FOREIGN KEY (direccion_id) REFERENCES public.usuario_direccion(id),
  CONSTRAINT fk_turno FOREIGN KEY (turno_id) REFERENCES public.usuarios_turnos(id)
);
CREATE TABLE public.usuarios_turnos (
  id integer NOT NULL DEFAULT nextval('usuarios_turnos_id_seq'::regclass),
  nombre character varying NOT NULL,
  hora_inicio time without time zone NOT NULL,
  hora_fin time without time zone NOT NULL,
  CONSTRAINT usuarios_turnos_pkey PRIMARY KEY (id)
);