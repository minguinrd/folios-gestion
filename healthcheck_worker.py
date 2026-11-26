"""Healthcheck del sync-worker: sale 0 si el latido es reciente.

Uso (compose): python healthcheck_worker.py [max_segundos]
El worker toca WORKER_HEARTBEAT en cada tick (1 min); un sync largo no lo
renueva hasta terminar, por eso el margen por defecto es amplio (10 min).
"""
import os
import sys
import time

ruta = os.environ.get('WORKER_HEARTBEAT', '/tmp/sync_worker_heartbeat')
maximo = int(sys.argv[1]) if len(sys.argv) > 1 else 600
try:
    edad = time.time() - os.path.getmtime(ruta)
except OSError:
    print(f'sin latido en {ruta}')
    sys.exit(1)
if edad > maximo:
    print(f'latido viejo: {int(edad)} s (máx {maximo})')
    sys.exit(1)
sys.exit(0)
