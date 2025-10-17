from marshmallow import Schema, fields, validate

class OrdenProduccionSchema(Schema):
    """
    Schema para la validación de datos de creación de órdenes de producción.
    """
    # Campos obligatorios para la creación
    producto_id = fields.Int(required=True)
    cantidad_planificada = fields.Decimal(as_string=True, required=True, validate=validate.Range(min=0.01, error="La cantidad debe ser mayor que cero."))
    fecha_planificada = fields.Date(required=True)
    receta_id = fields.Int(required=True)

    # Campos opcionales
    prioridad = fields.Str(validate=validate.OneOf(['BAJA', 'NORMAL', 'ALTA', 'URGENTE']), load_default='NORMAL')
    observaciones = fields.Str(allow_none=True)
    supervisor_responsable_id = fields.Int(required=False, allow_none=True)

    # Campos de solo lectura (generados por el sistema)
    id = fields.Int(dump_only=True)
    codigo = fields.Str(dump_only=True)
    usuario_creador_id = fields.Int(dump_only=True)
    fecha_inicio = fields.DateTime(dump_only=True, allow_none=True)
    fecha_fin = fields.DateTime(dump_only=True, allow_none=True)
    fecha_fin_estimada = fields.DateTime(dump_only=True, allow_none=True)
    fecha_aprobacion = fields.DateTime(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    linea_produccion = fields.Int(allow_none=True)
    super_op_id = fields.Int(allow_none=True)

    estado = fields.Str(required=False, validate=validate.OneOf([
        'PENDIENTE', 'APROBADA', 'EN_PROCESO', 'COMPLETADA', 'CANCELADA',
        'EN ESPERA', 'LISTA PARA PRODUCIR', 'EN LINEA 1', 'EN LINEA 2',
        'EN EMPAQUETADO', 'CONTROL DE CALIDAD', 'COMPLETADA', 'CONSOLIDADA'
    ]))
