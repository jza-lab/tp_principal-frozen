# -*- coding: utf-8 -*-
"""
Módulo centralizado para la gestión de estados en toda la aplicación.
Define constantes para los estados de pedidos, órdenes de producción y órdenes de compra,
así como funciones de utilidad para traducir entre representaciones de cadena y numéricas.
"""

# -----------------------------------------------------------------------------
# ESTADOS DE PEDIDOS DE VENTA (OV)
# -----------------------------------------------------------------------------

# --- Definiciones de constantes (string) ---
OV_PENDIENTE = 'PENDIENTE'
OV_PLANIFICADA = 'PLANIFICADA'
OV_EN_PROCESO = 'EN_PROCESO'
OV_ITEM_ALISTADO = 'ITEM_ALISTADO'
OV_LISTO_PARA_ENTREGA = 'LISTO_PARA_ENTREGA'
OV_EN_TRANSITO = 'EN_TRANSITO'
OV_RECEPCION_OK = 'RECEPCION_OK'
OV_RECEPCION_INCOMPLETA = 'RECEPCION_INCOMPLETA'
OV_PAGADA = 'PAGADA'
OV_IMPAGA = 'IMPAGA'
OV_RECHAZADA = 'RECHAZADA'
OV_CANCELADA = 'CANCELADO'
OV_DESPACHADO = 'DESPACHADO'
OV_ENTREGADO = 'ENTREGADO'
OV_COMPLETADO = 'COMPLETADO'


# --- Mapeo de cadena a entero para lógica de negocio y ordenamiento ---
OV_MAP_STRING_TO_INT = {
    OV_PENDIENTE: 10,
    OV_PLANIFICADA: 20,
    OV_EN_PROCESO: 30,
    OV_LISTO_PARA_ENTREGA: 50,
    OV_EN_TRANSITO: 60,
    OV_DESPACHADO: 70,
    OV_ENTREGADO: 80,
    OV_RECEPCION_OK: 90,
    OV_RECEPCION_INCOMPLETA: 100,
    OV_PAGADA: 110,
    OV_COMPLETADO: 120,
    OV_IMPAGA: -10,
    OV_RECHAZADA: -20,
    OV_CANCELADA: -30,
    OV_ITEM_ALISTADO: -40, # Agregado a terminales para orden
}

# --- Lista para la UI de filtros (Orden y nombres corregidos según 3.png) ---
OV_FILTROS_UI = [
    (OV_PENDIENTE, 'Pendiente'),
    (OV_PLANIFICADA, 'Planificada'),
    (OV_EN_PROCESO, 'En Proceso'),
    (OV_LISTO_PARA_ENTREGA, 'Listo Para Entregar'),
    (OV_EN_TRANSITO, 'En Transito'),
    (OV_COMPLETADO, 'Completado'),
    (OV_CANCELADA, 'Cancelada')
]


# -----------------------------------------------------------------------------
# ESTADOS DE ÓRDENES DE PRODUCCIÓN (OP)
# -----------------------------------------------------------------------------

# --- Definiciones de constantes (string) ---
OP_PENDIENTE = 'PENDIENTE'
OP_EN_ESPERA = 'EN_ESPERA'
OP_LISTA_PARA_PRODUCIR = 'LISTA_PARA_PRODUCIR' # Estado nuevo para el Kanban
OP_EN_PROCESO = 'EN_PROCESO'               # Estado nuevo para el Kanban
OP_CONTROL_CALIDAD = 'CONTROL_DE_CALIDAD'
OP_COMPLETADA = 'COMPLETADA'
OP_CANCELADA = 'CANCELADA'
OP_RECHAZADA = 'RECHAZADA'
OP_CONSOLIDADA = 'CONSOLIDADA'
OP_PLANIFICADA = 'PLANIFICADA'

OP_EN_LINEA_1 = 'EN_LINEA_1'
OP_EN_LINEA_2 = 'EN_LINEA_2'
OP_EN_EMPAQUETADO = 'EN_EMPAQUETADO'
OP_APROBADA = 'APROBADA' # Reemplazado por LISTA_PARA_PRODUCIR
OP_EN_PRODUCCION = 'EN_PRODUCCION' # Reemplazado por EN_PROCESO


# --- Mapeo de cadena a entero ---
OP_MAP_STRING_TO_INT = {
    OP_PENDIENTE: 10,
    OP_EN_ESPERA: 20,
    OP_PLANIFICADA: 30,
    OP_LISTA_PARA_PRODUCIR: 40,
    OP_EN_PROCESO: 50,
    OP_CONTROL_CALIDAD: 60,
    OP_COMPLETADA: 70,
    OP_CANCELADA: -10,
    OP_RECHAZADA: -20,
    OP_CONSOLIDADA: -30,

    # Deprecated mappings
    OP_APROBADA: 40, # Mapea al mismo que LISTA_PARA_PRODUCIR por compatibilidad
    OP_EN_PRODUCCION: 50, # Mapea al mismo que EN_PROCESO
    OP_EN_LINEA_1: 51,
    OP_EN_LINEA_2: 52,
    OP_EN_EMPAQUETADO: 55,
}

# --- Diccionario para la UI de columnas del Kanban ---
OP_KANBAN_COLUMNAS = {
    OP_EN_ESPERA: 'En Espera',
    OP_LISTA_PARA_PRODUCIR: 'Lista para Producir',
    OP_EN_PROCESO: 'En Proceso',
    OP_CONTROL_CALIDAD: 'Control de Calidad',
    OP_COMPLETADA: 'Completada',
}

# --- Lista para la UI de filtros (GENERAL) ---
OP_FILTROS_UI = [
    (OP_PENDIENTE, 'Pendiente'),
    (OP_EN_ESPERA, 'En Espera'),
    (OP_LISTA_PARA_PRODUCIR, 'Lista para Producir'),
    (OP_EN_PROCESO, 'En Proceso'),
    (OP_CONTROL_CALIDAD, 'Control De Calidad'),
    (OP_COMPLETADA, 'Completada'),
    (OP_CANCELADA, 'Cancelada'),
]


# -----------------------------------------------------------------------------
# ESTADOS DE ÓRDENES DE COMPRA (OC)
# -----------------------------------------------------------------------------

# --- Definiciones de constantes (string) ---
OC_PENDIENTE = 'PENDIENTE'
OC_RECHAZADA = 'RECHAZADA'
OC_CANCELADA = 'CANCELADA'
OC_EN_ESPERA_LLEGADA = 'EN_ESPERA_LLEGADA'
OC_APROBADA = 'APROBADA'
OC_COMPLETADA = 'COMPLETADA'
OC_EN_TRANSITO = 'EN_TRANSITO'
OC_RECEPCION_COMPLETA = 'RECEPCION_COMPLETA'
OC_RECEPCION_INCOMPLETA = 'RECEPCION_INCOMPLETA'
OC_PAGADA = 'PAGADA'


# --- Mapeo de cadena a entero ---
OC_MAP_STRING_TO_INT = {
    OC_PENDIENTE: 10,
    OC_APROBADA: 20,
    OC_EN_ESPERA_LLEGADA: 30,
    OC_EN_TRANSITO: 40,
    OC_RECEPCION_INCOMPLETA: 50,
    OC_RECEPCION_COMPLETA: 60,
    OC_COMPLETADA: 80, # Mantenido por si se usa como estado final lógico
    OC_PAGADA: 90,
    OC_RECHAZADA: -10,
    OC_CANCELADA: -20,
}

# --- Lista para la UI de filtros (Orden y nombres actualizados según imagen) ---
OC_FILTROS_UI = [
    (OC_PENDIENTE, 'Pendiente'),
    (OC_APROBADA, 'Aprobada'),
    (OC_EN_TRANSITO, 'En Transito'),
    (OC_RECEPCION_INCOMPLETA, 'Recepción Incompleta'),
    (OC_RECEPCION_COMPLETA, 'Recepción Completa'),
    (OC_RECHAZADA, 'Rechazada')
]

# -----------------------------------------------------------------------------
# FUNCIONES DE UTILIDAD
# -----------------------------------------------------------------------------

def traducir_a_int(estado_str, tipo_orden):
    """Traduce un estado de string a su correspondiente entero."""
    MAPS = {
        'OV': OV_MAP_STRING_TO_INT,
        'OP': OP_MAP_STRING_TO_INT,
        'OC': OC_MAP_STRING_TO_INT,
    }
    return MAPS.get(tipo_orden, {}).get(estado_str)

def traducir_a_cadena(estado_int, tipo_orden):
    """Traduce un estado de entero a su correspondiente string."""
    REVERSE_MAPS = {
        'OV': {v: k for k, v in OV_MAP_STRING_TO_INT.items()},
        'OP': {v: k for k, v in OP_MAP_STRING_TO_INT.items()},
        'OC': {v: k for k, v in OC_MAP_STRING_TO_INT.items()},
    }
    return REVERSE_MAPS.get(tipo_orden, {}).get(estado_int)
