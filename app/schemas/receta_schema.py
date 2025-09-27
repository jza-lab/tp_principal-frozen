from marshmallow import Schema, fields, validate

class RecetaIngredienteSchema(Schema):
    """
    Schema para la validación de los ingredientes de una receta.
    """
    id = fields.Int(dump_only=True)
    receta_id = fields.Int(required=True)
    id_insumo = fields.UUID(required=True)
    cantidad = fields.Float(required=True, validate=validate.Range(min=0.001, error="La cantidad debe ser mayor que cero."))
    unidad_medida = fields.Str(required=True)

class RecetaSchema(Schema):
    """
    Schema para la validación de los datos de una receta.
    """
    id = fields.Int(dump_only=True)
    nombre = fields.Str(required=True, validate=validate.Length(min=3))
    producto_id = fields.Int(required=True)
    version = fields.Str(required=True)
    descripcion = fields.Str(allow_none=True)
    rendimiento = fields.Float(allow_none=True)

    # El campo 'activa' y 'created_at' son gestionados por la base de datos o el modelo.
    activa = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

    # Campo para anidar los ingredientes al crear o actualizar una receta
    ingredientes = fields.List(fields.Nested(RecetaIngredienteSchema), required=False)