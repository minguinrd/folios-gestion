from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.models.marca import (
    DEPARTAMENTO_MAX,
    EXTENSIONES_PERMITIDAS,
    INSTITUCION_MAX,
    NOMBRE_MAX,
    SUBTITULO_MAX,
    SUFIJO_MAX,
)

_ARCHIVOS = ', '.join(e.upper() for e in EXTENSIONES_PERMITIDAS)


class MarcaForm(FlaskForm):
    nombre = StringField('Nombre de la aplicación', validators=[
        DataRequired(message='Este campo es obligatorio.'),
        Length(max=NOMBRE_MAX, message=f'Máximo {NOMBRE_MAX} caracteres.'),
    ])
    titulo_sufijo = StringField('Sufijo del título (pestaña del navegador)', validators=[
        Optional(),
        Length(max=SUFIJO_MAX, message=f'Máximo {SUFIJO_MAX} caracteres.'),
    ])
    subtitulo = StringField('Subtítulo', validators=[
        Optional(),
        Length(max=SUBTITULO_MAX, message=f'Máximo {SUBTITULO_MAX} caracteres.'),
    ])
    institucion = StringField('Institución', validators=[
        Optional(),
        Length(max=INSTITUCION_MAX, message=f'Máximo {INSTITUCION_MAX} caracteres.'),
    ])
    departamento = StringField('Departamento', validators=[
        Optional(),
        Length(max=DEPARTAMENTO_MAX, message=f'Máximo {DEPARTAMENTO_MAX} caracteres.'),
    ])
    logo = FileField('Logo', validators=[
        Optional(),
        FileAllowed(list(EXTENSIONES_PERMITIDAS), message=f'Logo: solo archivos {_ARCHIVOS}.'),
    ])
    favicon = FileField('Favicon', validators=[
        Optional(),
        FileAllowed(list(EXTENSIONES_PERMITIDAS), message=f'Favicon: solo archivos {_ARCHIVOS}.'),
    ])
    submit = SubmitField('Guardar')
