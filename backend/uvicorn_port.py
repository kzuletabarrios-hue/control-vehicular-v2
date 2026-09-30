#!/usr/local/bin/python
# Reemplaza al ejecutable `uvicorn` dentro de la imagen Docker.
# Railway guarda un "Custom Start Command" (uvicorn main:app ... --port $PORT)
# que ejecuta sin shell cuando el build es por Dockerfile, así que uvicorn
# recibe el texto literal "$PORT". Aquí se sustituye por la variable real.
import os
import sys

from uvicorn.main import main

sys.argv = [a.replace("$PORT", os.environ.get("PORT", "8000")) for a in sys.argv]
sys.exit(main())
