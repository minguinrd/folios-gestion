from flask_wtf import FlaskForm
from flask_wtf.file import FileRequired, MultipleFileField
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired


class EscaneoForm(FlaskForm):
    anio = SelectField('Año', coerce=int, validators=[
        DataRequired(message='Seleccione un año.'),
    ])
    # El tipo identifica al folio junto con año y número: sin él un escaneo
    # marcaba los folios de todos los tipos con ese número.
    tipo = SelectField('Tipo de certificado', coerce=int, validators=[
        DataRequired(message='Seleccione un tipo de certificado.'),
    ])
    # Sin FileAllowed a propósito: un solo no-JPG no debe rechazar el lote
    # entero (la spec exige "archivo no-jpg → rechazado con mensaje, continúa
    # con el resto"). El gate de nombre es NOMBRE_RE en app/services/escaneos.py:
    # los inválidos no se escriben en disco y se reportan uno a uno.
    archivos = MultipleFileField('Archivos JPG', validators=[
        FileRequired(message='Seleccione al menos un archivo.'),
    ])
    submit = SubmitField('Subir escaneos')
