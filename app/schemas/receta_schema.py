from marshmallow import Schema, fields, validate

class RecetaIngredienteSchema(Schema):
    """
    Schema para la validación de los ingredientes de una receta.
    """
    id = fields.Int(dump_only=True)
    receta_id = fields.Int(required=True)
    id_insumo = fields.UUID(required=True)
    cantidad = fields.Decimal(as_string=True, required=True, validate=validate.Range(min=0.001, error="La cantidad debe ser mayor que cero."))
    unidad_medida = fields.Str(required=True)
    tiempo_preparacion_minutos = fields.Int(allow_none=True, load_default=0)
    linea_compatible = fields.Str(allow_none=True, load_default='2')
    tiempo_prod_unidad_linea1 = fields.Decimal(as_string=True, allow_none=True, load_default=0)
    tiempo_prod_unidad_linea2 = fields.Decimal(as_string=True, allow_none=True, load_default=0)

class RecetaSchema(Schema):
    """
    Schema para la validación de los datos de una receta.
    """
    id = fields.Int(dump_only=True)
    nombre = fields.Str(required=True, validate=validate.Length(min=3))
    producto_id = fields.Int(required=True)
    version = fields.Str(required=True)
    descripcion = fields.Str(allow_none=True)
    rendimiento = fields.Decimal(as_string=True, allow_none=True)

    # El campo 'activa' y 'created_at' son gestionados por la base de datos o el modelo.
    activa = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

    # Campo para anidar los ingredientes al crear o actualizar una receta
    ingredientes = fields.List(fields.Nested(RecetaIngredienteSchema), required=False)
    operaciones = fields.List(fields.Dict(), required=False)