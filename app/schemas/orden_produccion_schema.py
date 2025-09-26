from marshmallow import Schema, fields, validate

class OrdenProduccionSchema(Schema):
    """
    Schema para la validación de datos de creación de órdenes de producción,
    alineado con la tabla 'ordenes_produccion' de db_setup.sql.
    """
    # Campos obligatorios para la creación
    producto_id = fields.Int(required=True)
    cantidad_planificada = fields.Float(required=True, validate=validate.Range(min=0.01, error="La cantidad debe ser mayor que cero."))
    fecha_planificada = fields.Date(required=True)
    receta_id = fields.Int(required=True)

    # Campos opcionales
    prioridad = fields.Str(validate=validate.OneOf(['BAJA', 'NORMAL', 'ALTA', 'URGENTE']), load_default='NORMAL')
    observaciones = fields.Str(allow_none=True)

    # Campos de solo lectura (generados por el sistema)
    id = fields.Int(dump_only=True)
    codigo = fields.Str(dump_only=True)
    estado = fields.Str(dump_only=True)
    usuario_creador_id = fields.Int(dump_only=True)
    fecha_inicio = fields.DateTime(dump_only=True, allow_none=True)
    fecha_fin = fields.DateTime(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)