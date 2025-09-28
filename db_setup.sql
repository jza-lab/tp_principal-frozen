CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ===============================
-- 1. FUNCIONES Y TRIGGERS GLOBALES
-- ===============================

-- Función para actualizar el timestamp de 'updated_at' automáticamente
CREATE OR REPLACE FUNCTION public.actualizar_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ===============================
-- 2. CREACIÓN DE TABLAS
-- ===============================

-- El orden de creación es importante para satisfacer las claves foráneas.

CREATE TABLE public.proveedores (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    contacto VARCHAR(100),
    telefono VARCHAR(20),
    email VARCHAR(100),
    direccion TEXT,
    cuit VARCHAR(15),
    condicion_iva VARCHAR(50),
    activo BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.productos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(50) NOT NULL,
    activo BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.usuarios (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  apellido VARCHAR(100) NOT NULL,
  rol VARCHAR(50) NOT NULL,
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla de Insumos (Catálogo)
CREATE TABLE public.insumos_catalogo (
  id_insumo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre VARCHAR(255) NOT NULL,
  codigo_interno VARCHAR(50) UNIQUE,
  unidad_medida VARCHAR(20) NOT NULL,
  categoria VARCHAR(100),
  stock_minimo NUMERIC(10, 2) DEFAULT 0.00,
  precio_unitario NUMERIC(10, 2),
  activo BOOLEAN DEFAULT true,
  dias_vida_util INTEGER,
  temperatura_conservacion NUMERIC,
  es_perecedero BOOLEAN DEFAULT true,
  creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla de Inventario de Insumos (Lotes)
CREATE TABLE public.insumos_inventario (
  id_lote UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_insumo UUID NOT NULL REFERENCES public.insumos_catalogo(id_insumo),
  cantidad_inicial NUMERIC(10, 2) NOT NULL,
  cantidad_actual NUMERIC(10, 2) NOT NULL,
  fecha_ingreso DATE NOT NULL,
  fecha_vencimiento DATE,
  costo_unitario NUMERIC(10, 2),
  proveedor_id INTEGER REFERENCES public.proveedores(id),
  codigo_lote_proveedor VARCHAR(100),
  estado VARCHAR(50) DEFAULT 'DISPONIBLE' CHECK (estado IN ('DISPONIBLE', 'AGOTADO', 'VENCIDO', 'EN_CUARENTENA', 'RECHAZADO')),
  creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.recetas (
  id SERIAL PRIMARY KEY,
  nombre VARCHAR(255) NOT NULL,
  producto_id INTEGER NOT NULL REFERENCES public.productos(id),
  version VARCHAR(50) NOT NULL,
  descripcion TEXT,
  rendimiento NUMERIC(10, 2),
  activa BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(producto_id, version)
);

CREATE TABLE public.receta_ingredientes (
  id SERIAL PRIMARY KEY,
  receta_id INTEGER NOT NULL REFERENCES public.recetas(id) ON DELETE CASCADE,
  id_insumo UUID NOT NULL REFERENCES public.insumos_catalogo(id_insumo),
  cantidad NUMERIC(10, 2) NOT NULL,
  unidad_medida VARCHAR(20) NOT NULL
);

CREATE TABLE public.etapas_produccion (
    id SERIAL PRIMARY KEY,
    etapa VARCHAR(255) NOT NULL,
    orden_produccion_id INTEGER NOT NULL REFERENCES public.ordenes_produccion(id),
    fecha_inicio TIMESTAMP WITH TIME ZONE,
    fecha_fin TIMESTAMP WITH TIME ZONE,
    cantidad_procesada NUMERIC(10, 2),
    desperdicio NUMERIC(10, 2) DEFAULT 0.00,
    operario_id INTEGER REFERENCES public.usuarios(id),
    observaciones TEXT,
    estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    temperatura_registrada NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.asistencias (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES public.usuarios(id),
    tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA')),
    fecha_hora TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    observaciones TEXT
);

CREATE TABLE public.ordenes_produccion (
  id SERIAL PRIMARY KEY,
  codigo VARCHAR(50) NOT NULL UNIQUE,
  producto_id INTEGER NOT NULL REFERENCES public.productos(id),
  receta_id INTEGER NOT NULL REFERENCES public.recetas(id),
  cantidad_planificada NUMERIC(10, 2) NOT NULL,
  estado VARCHAR(50) NOT NULL DEFAULT 'PLANIFICADA',
  fecha_planificada DATE NOT NULL,
  fecha_inicio TIMESTAMP WITH TIME ZONE,
  fecha_fin TIMESTAMP WITH TIME ZONE,
  usuario_creador_id INTEGER REFERENCES public.usuarios(id),
  observaciones TEXT,
  prioridad VARCHAR(20) DEFAULT 'NORMAL',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.pedidos (
    id SERIAL PRIMARY KEY,
    nombre_cliente VARCHAR(255) NOT NULL,
    fecha_solicitud DATE NOT NULL,
    estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    orden_produccion_id INT REFERENCES public.ordenes_produccion(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.pedido_items (
    id SERIAL PRIMARY KEY,
    pedido_id INT NOT NULL REFERENCES public.pedidos(id) ON DELETE CASCADE,
    producto_id INT NOT NULL REFERENCES public.productos(id),
    cantidad REAL NOT NULL,
    UNIQUE(pedido_id, producto_id)
);

CREATE TABLE public.movimientos_stock (
  id SERIAL PRIMARY KEY,
  id_insumo UUID NOT NULL REFERENCES public.insumos_catalogo(id_insumo),
  id_lote UUID NOT NULL REFERENCES public.insumos_inventario(id_lote),
  tipo_movimiento VARCHAR(20) NOT NULL CHECK (tipo_movimiento IN ('ENTRADA', 'SALIDA', 'AJUSTE')),
  cantidad NUMERIC(10, 2) NOT NULL,
  orden_produccion_id INTEGER REFERENCES public.ordenes_produccion(id),
  usuario_id INTEGER REFERENCES public.usuarios(id),
  motivo VARCHAR(255),
  fecha TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===============================
-- 3. TRIGGERS PARA 'updated_at'
-- ===============================

CREATE TRIGGER trigger_pedidos_updated_at BEFORE UPDATE ON public.pedidos FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp_updated_at();
CREATE TRIGGER trigger_insumos_catalogo_updated_at BEFORE UPDATE ON public.insumos_catalogo FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp_updated_at();
CREATE TRIGGER trigger_insumos_inventario_updated_at BEFORE UPDATE ON public.insumos_inventario FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp_updated_at();
CREATE TRIGGER trigger_ordenes_produccion_updated_at BEFORE UPDATE ON public.ordenes_produccion FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp_updated_at();
-- (Se pueden añadir triggers para el resto de las tablas si es necesario)

-- ===============================
-- 4. VISTAS ÚTILES (VIEWS)
-- ===============================

CREATE OR REPLACE VIEW v_stock_consolidado AS
SELECT
    ic.id_insumo,
    ic.nombre,
    ic.codigo_interno,
    ic.unidad_medida,
    ic.stock_minimo,
    COALESCE(SUM(ii.cantidad_actual) FILTER (WHERE ii.estado = 'DISPONIBLE'), 0) as stock_actual
FROM public.insumos_catalogo ic
LEFT JOIN public.insumos_inventario ii ON ic.id_insumo = ii.id_insumo
GROUP BY ic.id_insumo;

CREATE OR REPLACE VIEW v_stock_con_alertas AS
SELECT
    vsc.id_insumo,
    vsc.nombre,
    vsc.codigo_interno,
    vsc.stock_actual,
    vsc.stock_minimo,
    vsc.unidad_medida,
    CASE
        WHEN vsc.stock_actual <= vsc.stock_minimo THEN 'CRITICO'
        WHEN vsc.stock_actual <= (vsc.stock_minimo * 1.2) THEN 'BAJO'
        ELSE 'OK'
    END as estado_stock
FROM v_stock_consolidado vsc;

-- ===============================
-- 5. FUNCIONES AVANZADAS
-- ===============================

-- Función para registrar una entrada de stock (nuevo lote)
CREATE OR REPLACE FUNCTION public.registrar_entrada_lote(
    p_id_insumo UUID,
    p_cantidad_inicial NUMERIC,
    p_fecha_ingreso DATE,
    p_costo_unitario NUMERIC,
    p_id_proveedor INT,
    p_id_usuario INT,
    p_fecha_vencimiento DATE DEFAULT NULL,
    p_codigo_lote_proveedor TEXT DEFAULT NULL
)
RETURNS public.insumos_inventario AS $$
DECLARE
    nuevo_lote public.insumos_inventario;
BEGIN
    INSERT INTO public.insumos_inventario (
        id_insumo, cantidad_inicial, cantidad_actual, fecha_ingreso, costo_unitario, proveedor_id, fecha_vencimiento, codigo_lote_proveedor
    ) VALUES (
        p_id_insumo, p_cantidad_inicial, p_cantidad_inicial, p_fecha_ingreso, p_costo_unitario, p_id_proveedor, p_fecha_vencimiento, p_codigo_lote_proveedor
    ) RETURNING * INTO nuevo_lote;

    INSERT INTO public.movimientos_stock (
        id_insumo, id_lote, tipo_movimiento, cantidad, usuario_id, motivo
    ) VALUES (
        p_id_insumo, nuevo_lote.id_lote, 'ENTRADA', p_cantidad_inicial, p_id_usuario, 'Ingreso de nuevo lote'
    );

    RETURN nuevo_lote;
END;
$$ LANGUAGE plpgsql;


-- Función para descontar stock de lotes (FIFO)
CREATE OR REPLACE FUNCTION public.descontar_stock_fifo(
    p_id_insumo UUID,
    p_cantidad_a_descontar NUMERIC,
    p_id_orden_produccion INT,
    p_id_usuario INT
)
RETURNS NUMERIC AS $$
DECLARE
    lote_actual RECORD;
    cantidad_descontada NUMERIC;
    cantidad_restante_a_descontar NUMERIC := p_cantidad_a_descontar;
BEGIN
    FOR lote_actual IN
        SELECT * FROM public.insumos_inventario
        WHERE id_insumo = p_id_insumo AND cantidad_actual > 0 AND estado = 'DISPONIBLE'
        ORDER BY fecha_vencimiento ASC, fecha_ingreso ASC
    LOOP
        IF cantidad_restante_a_descontar <= 0 THEN
            EXIT;
        END IF;

        IF lote_actual.cantidad_actual >= cantidad_restante_a_descontar THEN
            cantidad_descontada := cantidad_restante_a_descontar;
        ELSE
            cantidad_descontada := lote_actual.cantidad_actual;
        END IF;

        UPDATE public.insumos_inventario
        SET cantidad_actual = cantidad_actual - cantidad_descontada
        WHERE id_lote = lote_actual.id_lote;

        INSERT INTO public.movimientos_stock (
            id_insumo, id_lote, tipo_movimiento, cantidad, orden_produccion_id, usuario_id, motivo
        ) VALUES (
            p_id_insumo, lote_actual.id_lote, 'SALIDA', cantidad_descontada, p_id_orden_produccion, p_id_usuario, 'Consumo para producción'
        );

        cantidad_restante_a_descontar := cantidad_restante_a_descontar - cantidad_descontada;
    END LOOP;

    IF cantidad_restante_a_descontar > 0 THEN
        RAISE EXCEPTION 'Stock insuficiente para el insumo ID %. Faltan % unidades.', p_id_insumo, cantidad_restante_a_descontar;
    END IF;

    RETURN p_cantidad_a_descontar;
END;
$$ LANGUAGE plpgsql;

-- Función para crear un pedido con sus ítems de forma transaccional
CREATE OR REPLACE FUNCTION public.crear_pedido_con_items(
    p_nombre_cliente VARCHAR,
    p_fecha_solicitud DATE,
    p_items JSONB
)
RETURNS INT AS $$
DECLARE
    nuevo_pedido_id INT;
    item JSONB;
BEGIN
    -- Insertar el pedido principal y obtener su ID
    INSERT INTO public.pedidos (nombre_cliente, fecha_solicitud, estado)
    VALUES (p_nombre_cliente, p_fecha_solicitud, 'PENDIENTE')
    RETURNING id INTO nuevo_pedido_id;

    -- Iterar sobre los ítems e insertarlos
    FOR item IN SELECT * FROM jsonb_array_elements(p_items)
    LOOP
        INSERT INTO public.pedido_items (pedido_id, producto_id, cantidad)
        VALUES (
            nuevo_pedido_id,
            (item->>'producto_id')::INT,
            (item->>'cantidad')::REAL
        );
    END LOOP;

    RETURN nuevo_pedido_id;
END;
$$ LANGUAGE plpgsql;
