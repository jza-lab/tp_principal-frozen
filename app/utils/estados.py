# app/utils/estados.py

# --- Órdenes de Venta (Rango: 0-149) ---
OV_PENDIENTE = 5
OV_PLANIFICADA = 15
OV_EN_PROCESO = 20
OV_LISTA_PARA_ENTREGAR = 32
OV_EN_TRANSITO = 40
OV_RECEPCION_OK = 60
OV_RECEPCION_INCOMPLETA = 62
OV_PAGADA = 70
OV_IMPAGA = 75
OV_RECHAZADA = 1
OV_CANCELADA = 3
# Estados internos o de items
OV_ITEM_ALISTADO = 28
OV_LISTO_PARA_ARMAR = 30 # Estado agregado del pedido

# --- Órdenes de Compra (Rango: 150-299) ---
OC_PENDIENTE = 150
OC_RECHAZADA = 151
OC_CANCELADA = 153
OC_EN_ESPERA_LLEGADA = 154
OC_APROBADA = 156
OC_RECIBIDA = 160
OC_COMPLETADA = 190

# --- Órdenes de Producción (Rango: 300-449) ---
OP_PENDIENTE = 300
OP_RECHAZADA = 301
OP_CANCELADA = 303
OP_EN_ESPERA = 304  # Esperando stock/insumos
OP_APROBADA = 306
OP_PLANIFICADA = 315
OP_EN_PRODUCCION = 320
OP_CONTROL_DE_CALIDAD = 325
OP_COMPLETADA = 390
OP_CONSOLIDADA = 395 # Nuevo estado para OPs fusionadas
# Estados intermedios de producción que el frontend podría usar
OP_EN_LINEA_1 = 321
OP_EN_LINEA_2 = 322
OP_EN_EMPAQUETADO = 323

# --- Estado Desconocido ---
DESCONOCIDO = 999


# --- Mapeo Global de Entero a Cadena (para DB y Frontend) ---
INT_A_CADENA = {
    # Órdenes de Venta
    OV_PENDIENTE: 'PENDIENTE',
    OV_PLANIFICADA: 'PLANIFICADA',
    OV_EN_PROCESO: 'EN_PROCESO',
    OV_LISTA_PARA_ENTREGAR: 'LISTO_PARA_ENTREGAR',
    OV_EN_TRANSITO: 'EN_TRANSITO',
    OV_RECEPCION_OK: 'RECEPCION OK',
    OV_RECEPCION_INCOMPLETA: 'RECEPCION INCOMPLETA',
    OV_PAGADA: 'PAGADA',
    OV_IMPAGA: 'IMPAGA',
    OV_RECHAZADA: 'RECHAZADA',
    OV_CANCELADA: 'CANCELADA',
    OV_ITEM_ALISTADO: 'ALISTADO',
    OV_LISTO_PARA_ARMAR: 'LISTO_PARA_ARMAR',
    60: 'COMPLETADO', # Compatibilidad con estado antiguo de OV

    # Órdenes de Compra
    OC_PENDIENTE: 'PENDIENTE',
    OC_RECHAZADA: 'RECHAZADA',
    OC_CANCELADA: 'CANCELADA',
    OC_EN_ESPERA_LLEGADA: 'EN ESPERA DE LLEGADA',
    OC_APROBADA: 'APROBADA',
    OC_RECIBIDA: 'RECIBIDA',
    OC_COMPLETADA: 'COMPLETADA',

    # Órdenes de Producción
    OP_PENDIENTE: 'PENDIENTE',
    OP_RECHAZADA: 'RECHAZADA',
    OP_CANCELADA: 'CANCELADA',
    OP_EN_ESPERA: 'EN_ESPERA',
    OP_APROBADA: 'APROBADA',
    OP_PLANIFICADA: 'PLANIFICADA',
    OP_EN_PRODUCCION: 'EN PRODUCCION',
    OP_CONTROL_DE_CALIDAD: 'CONTROL_DE_CALIDAD',
    OP_COMPLETADA: 'COMPLETADA',
    OP_CONSOLIDADA: 'CONSOLIDADA',
    OP_EN_LINEA_1: 'EN_LINEA_1',
    OP_EN_LINEA_2: 'EN_LINEA_2',
    OP_EN_EMPAQUETADO: 'EN_EMPAQUETADO',
    
    DESCONOCIDO: 'DESCONOCIDO'
}

# --- Mapeo Inverso de Cadena a Entero ---
CADENA_A_INT = {v: k for k, v in INT_A_CADENA.items()}
# Casos especiales y compatibilidad
CADENA_A_INT['COMPLETADO'] = 60
CADENA_A_INT['EN ESPERA'] = OP_EN_ESPERA
CADENA_A_INT['EN PRODUCCION'] = OP_EN_PRODUCCION
CADENA_A_INT['CONTROL DE CALIDAD'] = OP_CONTROL_DE_CALIDAD


# --- Funciones de Ayuda ---
def traducir_a_cadena(estado_int):
    """Traduce un estado entero a su cadena correspondiente."""
    return INT_A_CADENA.get(estado_int, 'DESCONOCIDO')

def traducir_a_int(estado_cadena):
    """Traduce una cadena de estado a su entero correspondiente de forma robusta."""
    if estado_cadena is None:
        return DESCONOCIDO
    
    estado_upper = str(estado_cadena).upper()
    
    # Búsqueda 1: Coincidencia exacta
    if estado_upper in CADENA_A_INT:
        return CADENA_A_INT[estado_upper]
    
    # Búsqueda 2: Normalizando espacios a guiones bajos
    estado_normalizado = estado_upper.replace(" ", "_")
    if estado_normalizado in CADENA_A_INT:
        return CADENA_A_INT[estado_normalizado]
        
    return DESCONOCIDO

def traducir_lista_a_cadena(lista_objetos):
    """Itera una lista de diccionarios y traduce el campo 'estado' de int a cadena."""
    if not lista_objetos:
        return []
    for obj in lista_objetos:
        if obj and 'estado' in obj and isinstance(obj['estado'], int):
            obj['estado'] = traducir_a_cadena(obj['estado'])
    return lista_objetos

def traducir_objeto_a_cadena(obj):
    """Traduce el campo 'estado' de un diccionario de int a cadena."""
    if obj and 'estado' in obj and isinstance(obj['estado'], int):
        obj['estado'] = traducir_a_cadena(obj['estado'])
    return obj
