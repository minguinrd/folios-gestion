#!/usr/bin/env python3
"""Sube docker-hub-description.md como descripción del repo en Docker Hub.

`docker push` solo sube la imagen: la página del repositorio (descripción
larga y corta) se editaba a mano y quedaba atrasada respecto a la imagen.

Credenciales SOLO por entorno (nunca se leen de ~/.docker/config.json):
  DOCKERHUB_USERNAME   usuario de Docker Hub
  DOCKERHUB_TOKEN      Personal Access Token con permiso Read & Write
                       (Docker Hub → Account settings → Personal access tokens)
Opcional:
  DOCKERHUB_REPO       default m809/folios-gestion

Uso:
  scripts/dockerhub_descripcion.py            # actualiza
  scripts/dockerhub_descripcion.py --dry-run  # muestra qué enviaría
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / 'docker-hub-description.md'
REPO_DEFAULT = 'm809/folios-gestion'
API = 'https://hub.docker.com/v2'

# Docker Hub limita la descripción corta a 100 caracteres.
DESCRIPCION_CORTA = ('Seguimiento de folios de certificados de salud: recepción, '
                     'entregas, devoluciones y reportes.')
MAX_CORTA = 100
MAX_LARGA = 25000


def payload():
    larga = ARCHIVO.read_text(encoding='utf-8')
    if len(DESCRIPCION_CORTA) > MAX_CORTA:
        raise ValueError(f'descripción corta de {len(DESCRIPCION_CORTA)} > {MAX_CORTA} caracteres')
    if len(larga) > MAX_LARGA:
        raise ValueError(f'{ARCHIVO.name} supera {MAX_LARGA} caracteres')
    return {'description': DESCRIPCION_CORTA, 'full_description': larga}


def _json(url, data, method='POST', token=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method=method,
                                 headers={'Content-Type': 'application/json',
                                          'User-Agent': 'folios-release-script'})
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or b'{}')


def obtener_token(usuario, pat):
    """JWT de la API de Hub a partir del PAT."""
    datos = _json(f'{API}/auth/token', {'identifier': usuario, 'secret': pat})
    return datos.get('access_token') or datos['token']


def main(argv):
    repo = os.environ.get('DOCKERHUB_REPO', REPO_DEFAULT)
    datos = payload()
    if '--dry-run' in argv:
        print(f'[dockerhub] repo: {repo}')
        print(f'[dockerhub] corta ({len(datos["description"])}): {datos["description"]}')
        print(f'[dockerhub] larga: {len(datos["full_description"])} caracteres de {ARCHIVO.name}')
        return 0

    usuario = os.environ.get('DOCKERHUB_USERNAME')
    pat = os.environ.get('DOCKERHUB_TOKEN')
    if not usuario or not pat:
        print('[dockerhub] Faltan DOCKERHUB_USERNAME y/o DOCKERHUB_TOKEN en el entorno.',
              file=sys.stderr)
        return 2
    try:
        token = obtener_token(usuario, pat)
        _json(f'{API}/repositories/{repo}/', datos, method='PATCH', token=token)
    except urllib.error.HTTPError as exc:
        # El cuerpo de error de Hub no incluye el token; se muestra para diagnóstico.
        cuerpo = exc.read().decode(errors='replace')[:300]
        print(f'[dockerhub] ERROR HTTP {exc.code}: {cuerpo}', file=sys.stderr)
        if exc.code in (401, 403):
            print('[dockerhub] Revise que el token tenga permiso Read & Write sobre el repo.',
                  file=sys.stderr)
        return 1
    print(f'[dockerhub] Descripción de {repo} actualizada desde {ARCHIVO.name}.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
