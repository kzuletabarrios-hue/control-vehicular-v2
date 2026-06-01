#!/usr/bin/env python3
"""
SCRIPT DE MIGRACIÓN
Google Sheets (CSV) → PostgreSQL (Control Vehicular v2)

Uso:
  1. Exportar cada hoja del Google Sheets como CSV
  2. Colocar los archivos en la carpeta ./csv_exports/
  3. Renombrar según la tabla (ver ARCHIVOS_ESPERADOS abajo)
  4. Ejecutar: python migrate.py

Requiere:
  pip install psycopg2-binary pandas python-dotenv tqdm
"""

import os
import sys
import uuid
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from datetime import datetime, date
from pathlib import Path

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
CSV_DIR = Path("./csv_exports")

# Mapeo: nombre_del_archivo_csv → tabla_destino
ARCHIVOS = {
    "FLOTA PROPIA.csv":        "flota_propia",
    "CONDUCTORES.csv":         "conductores",
    "DISTRIBUCION.csv":        "distribucion",
    "PROVEEDORES.csv":         "proveedores",
    "VISITANTES.csv":          "visitantes",
    "REGISTROS.csv":           "registros",
    "PROVEEDORES BD.csv":      "bd_proveedores",
    "CONTROL DE ACCESO.csv":   "control_acceso",
    "BD_CONTROL ACCESO.csv":   "bd_control_acceso",
}

# Mapeo de columnas originales AppSheet → columnas PostgreSQL
COLUMNAS = {
    "flota_propia": {
        "IDENTIFICACIÓN":        "id",
        "FECHA":                 "fecha",
        "PLACA":                 "placa",
        "CODIGO":                "codigo_conductor",
        "CONDUCTOR":             "conductor",
        "N° DE PALLETS":         "n_pallets",
        "N° DE CONTENEDORES":    "n_contenedores",
        "CANT. VOLUMEN EXTERNO": "cant_volumen_externo",
        "MUELLE DE CARGUE":      "muelle_cargue",
        "TIENDA 1":              "tienda_1_nombre",
        "TIENDA 2":              "tienda_2_nombre",
        "TIENDA 3":              "tienda_3_nombre",
        "TIENDA 4":              "tienda_4_nombre",
        "TIENDA 5":              "tienda_5_nombre",
        "ULTIMA TIENDA":         "ultima_tienda_nombre",
        "PROTOCOLO":             "protocolo",
        "SELLO":                 "sello",
        "SELLO DE ENTRADA":      "sello_entrada",
        "HORA DE SALIDA DE MUELLE": "hora_salida_muelle",
        "TEMPERATURA":           "temperatura",
        "HORA DE SALIDA DE CEDI": "hora_salida_cedi",
        "HORA DE LLEGADA":       "hora_llegada",
        "OBSERVACION":           "observacion",
    },
    "conductores": {
        "CODIGO":    "codigo",
        "CONDUCTOR": "conductor",
        "N° CEDULA": "n_cedula",
        "CELULAR":   "celular",
        "TIPO":      "tipo",
    },
    "distribucion": {
        "Name": "name",
    },
    "bd_proveedores": {
        "NOMBRE":   "nombre",
        "NIT":      "nit",
        "CONTACTO": "contacto",
        "CELULAR":  "celular",
    },
    "bd_control_acceso": {
        "CEDULA":      "cedula",
        "NOMBRE":      "nombre",
        "CONTRATISTA": "contratista",
        "ESTADO":      "estado",
    },
    "control_acceso": {
        "FECHA":          "fecha",
        "CEDULA":         "cedula_raw",
        "NOMBRE":         "nombre",
        "CONTRATISTA":    "contratista",
        "HORA DE INGRESO":"hora_ingreso",
        "HORA DE SALIDA": "hora_salida",
        "OBSERVACIONES":  "observaciones",
    },
    "visitantes": {
        "FECHA":          "fecha",
        "NOMBRE":         "nombre",
        "N° CEDULA":      "cedula",
        "EMPRESA":        "empresa",
        "HORA DE INGRESO":"hora_ingreso",
        "HORA DE SALIDA": "hora_salida",
        "OBSERVACIONES":  "observaciones",
    },
    "proveedores": {
        "FECHA":                    "fecha",
        "PLACA DE VEHICULO":        "placa_vehiculo",
        "NOMBRE CONDUCTOR":         "nombre_conductor",
        "TIPO DE VEHICULO":         "tipo_vehiculo",
        "EMPRESA":                  "empresa",
        "MUELLE DE DESCARGUE":      "muelle_descargue",
        "CARGA COMPARTIDA":         "carga_compartida",
        "HORA DE INGRESO":          "hora_ingreso",
        "HORA DE SALIDA":           "hora_salida",
        "ACTIVIDAD A DESARROLLAR":  "actividad_a_desarrollar",
        "DEPENDENCIA QUE AUTORIZA": "dependencia_autoriza",
        "FECHA DE PAGO DE ARL":     "fecha_pago_arl",
        "OBSERVACIONES":            "observaciones",
    },
}


def limpiar_valor(val):
    if pd.isna(val) or val == "" or val == "—":
        return None
    if isinstance(val, float) and val == int(val):
        return int(val)
    return val


def parse_fecha(val):
    if pd.isna(val) or not val:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_hora(val):
    if pd.isna(val) or not val:
        return None
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


class Migrador:
    def __init__(self, db_url: str):
        self.conn = psycopg2.connect(db_url)
        self.cur  = self.conn.cursor()
        self.errores = []
        self.totales = {}

    def close(self):
        self.cur.close()
        self.conn.close()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    # ── MAESTROS PRIMERO (sin FK) ─────────────────────────────────

    def migrar_conductores(self, df: pd.DataFrame):
        self.log("Migrando CONDUCTORES...")
        col_map = COLUMNAS["conductores"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        for _, row in df.iterrows():
            filas.append((
                str(uuid.uuid4()),
                int(row["codigo"]) if "codigo" in row and not pd.isna(row["codigo"]) else None,
                limpiar_valor(row.get("conductor")),
                limpiar_valor(row.get("n_cedula")),
                limpiar_valor(row.get("celular")),
                limpiar_valor(row.get("tipo")),
                True,
            ))
        execute_values(self.cur,
            "INSERT INTO conductores (id,codigo,conductor,n_cedula,celular,tipo,activo) VALUES %s ON CONFLICT (codigo) DO NOTHING",
            filas)
        self.conn.commit()
        self.totales["conductores"] = len(filas)
        self.log(f"  → {len(filas)} conductores migrados")

    def migrar_distribucion(self, df: pd.DataFrame):
        self.log("Migrando DISTRIBUCIÓN (tiendas)...")
        col_map = COLUMNAS["distribucion"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        nombres = df["name"].dropna().unique().tolist() if "name" in df.columns else []
        filas = [(str(uuid.uuid4()), n.strip()) for n in nombres if n.strip()]
        execute_values(self.cur,
            "INSERT INTO distribucion (id, name) VALUES %s ON CONFLICT (name) DO NOTHING",
            filas)
        self.conn.commit()
        self.totales["distribucion"] = len(filas)
        self.log(f"  → {len(filas)} tiendas migradas")

    def migrar_bd_proveedores(self, df: pd.DataFrame):
        self.log("Migrando BD PROVEEDORES...")
        col_map = COLUMNAS["bd_proveedores"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        for _, row in df.iterrows():
            nombre = limpiar_valor(row.get("nombre"))
            if not nombre:
                continue
            filas.append((
                str(uuid.uuid4()),
                nombre,
                limpiar_valor(row.get("nit")),
                limpiar_valor(row.get("contacto")),
                limpiar_valor(row.get("celular")),
                True,
            ))
        execute_values(self.cur,
            "INSERT INTO bd_proveedores (id,nombre,nit,contacto,celular,activo) VALUES %s",
            filas)
        self.conn.commit()
        self.totales["bd_proveedores"] = len(filas)
        self.log(f"  → {len(filas)} proveedores BD migrados")

    def migrar_bd_control_acceso(self, df: pd.DataFrame):
        self.log("Migrando BD CONTROL ACCESO...")
        col_map = COLUMNAS["bd_control_acceso"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        for _, row in df.iterrows():
            cedula = limpiar_valor(row.get("cedula"))
            nombre = limpiar_valor(row.get("nombre"))
            if not cedula or not nombre:
                continue
            try:
                cedula = int(float(str(cedula)))
            except (ValueError, TypeError):
                continue
            filas.append((
                cedula,
                nombre,
                limpiar_valor(row.get("contratista")),
                limpiar_valor(row.get("estado")) or "ACTIVO",
            ))
        execute_values(self.cur,
            "INSERT INTO bd_control_acceso (cedula,nombre,contratista,estado) VALUES %s ON CONFLICT (cedula) DO NOTHING",
            filas)
        self.conn.commit()
        self.totales["bd_control_acceso"] = len(filas)
        self.log(f"  → {len(filas)} personas BD control acceso migradas")

    # ── TABLAS OPERATIVAS ─────────────────────────────────────────

    def _tienda_id(self, nombre: str) -> str | None:
        if not nombre or pd.isna(nombre):
            return None
        self.cur.execute("SELECT id FROM distribucion WHERE name = %s", (str(nombre).strip(),))
        r = self.cur.fetchone()
        return str(r[0]) if r else None

    def _conductor_codigo(self, codigo) -> int | None:
        if not codigo or pd.isna(codigo):
            return None
        try:
            return int(float(str(codigo)))
        except (ValueError, TypeError):
            return None

    def migrar_flota(self, df: pd.DataFrame):
        self.log("Migrando FLOTA PROPIA...")
        col_map = COLUMNAS["flota_propia"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        errores = 0
        for _, row in df.iterrows():
            try:
                fila = (
                    str(uuid.uuid4()),
                    parse_fecha(row.get("fecha")) or date.today(),
                    limpiar_valor(row.get("placa")) or "SIN PLACA",
                    self._conductor_codigo(row.get("codigo_conductor")),
                    limpiar_valor(row.get("conductor")),
                    limpiar_valor(row.get("n_pallets")),
                    limpiar_valor(row.get("n_contenedores")),
                    limpiar_valor(row.get("cant_volumen_externo")),
                    limpiar_valor(row.get("muelle_cargue")),
                    self._tienda_id(row.get("tienda_1_nombre")),
                    self._tienda_id(row.get("tienda_2_nombre")),
                    self._tienda_id(row.get("tienda_3_nombre")),
                    self._tienda_id(row.get("tienda_4_nombre")),
                    self._tienda_id(row.get("tienda_5_nombre")),
                    self._tienda_id(row.get("ultima_tienda_nombre")),
                    limpiar_valor(row.get("ultima_tienda_nombre")),
                    limpiar_valor(row.get("protocolo")),
                    limpiar_valor(row.get("sello")),
                    limpiar_valor(row.get("sello_entrada")),
                    parse_hora(row.get("hora_salida_muelle")),
                    limpiar_valor(row.get("temperatura")),
                    parse_hora(row.get("hora_salida_cedi")),
                    parse_hora(row.get("hora_llegada")),
                    limpiar_valor(row.get("observacion")),
                )
                filas.append(fila)
            except Exception as e:
                errores += 1
                self.errores.append(f"flota_propia fila {_}: {e}")

        execute_values(self.cur, """
            INSERT INTO flota_propia (
                id,fecha,placa,codigo_conductor,conductor,
                n_pallets,n_contenedores,cant_volumen_externo,muelle_cargue,
                tienda_1,tienda_2,tienda_3,tienda_4,tienda_5,
                ultima_tienda,ultima_tienda_visitada,
                protocolo,sello,sello_entrada,
                hora_salida_muelle,temperatura,hora_salida_cedi,hora_llegada,
                observacion
            ) VALUES %s ON CONFLICT DO NOTHING
        """, filas)
        self.conn.commit()
        self.totales["flota_propia"] = len(filas)
        self.log(f"  → {len(filas)} registros flota migrados ({errores} errores)")

    def migrar_control_acceso(self, df: pd.DataFrame):
        self.log("Migrando CONTROL DE ACCESO...")
        col_map = COLUMNAS["control_acceso"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        for _, row in df.iterrows():
            cedula_raw = limpiar_valor(row.get("cedula_raw"))
            cedula = None
            if cedula_raw:
                try:
                    cedula = int(float(str(cedula_raw)))
                    self.cur.execute("SELECT 1 FROM bd_control_acceso WHERE cedula=%s", (cedula,))
                    if not self.cur.fetchone():
                        cedula = None
                except (ValueError, TypeError):
                    cedula = None
            filas.append((
                str(uuid.uuid4()),
                parse_fecha(row.get("fecha")) or date.today(),
                cedula,
                limpiar_valor(row.get("nombre")),
                limpiar_valor(row.get("contratista")),
                parse_hora(row.get("hora_ingreso")),
                parse_hora(row.get("hora_salida")),
                limpiar_valor(row.get("observaciones")),
            ))
        execute_values(self.cur,
            "INSERT INTO control_acceso (id,fecha,cedula,nombre,contratista,hora_ingreso,hora_salida,observaciones) VALUES %s",
            filas)
        self.conn.commit()
        self.totales["control_acceso"] = len(filas)
        self.log(f"  → {len(filas)} registros acceso migrados")

    def migrar_visitantes(self, df: pd.DataFrame):
        self.log("Migrando VISITANTES...")
        col_map = COLUMNAS["visitantes"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        for _, row in df.iterrows():
            filas.append((
                str(uuid.uuid4()),
                parse_fecha(row.get("fecha")) or date.today(),
                limpiar_valor(row.get("nombre")),
                limpiar_valor(row.get("cedula")),
                limpiar_valor(row.get("empresa")),
                parse_hora(row.get("hora_ingreso")),
                parse_hora(row.get("hora_salida")),
                limpiar_valor(row.get("observaciones")),
            ))
        execute_values(self.cur,
            "INSERT INTO visitantes (id,fecha,nombre,cedula,empresa,hora_ingreso,hora_salida,observaciones) VALUES %s",
            filas)
        self.conn.commit()
        self.totales["visitantes"] = len(filas)
        self.log(f"  → {len(filas)} visitantes migrados")

    def migrar_proveedores(self, df: pd.DataFrame):
        self.log("Migrando PROVEEDORES (TGN)...")
        col_map = COLUMNAS["proveedores"]
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        filas = []
        for _, row in df.iterrows():
            filas.append((
                str(uuid.uuid4()),
                parse_fecha(row.get("fecha")) or date.today(),
                limpiar_valor(row.get("placa_vehiculo")),
                limpiar_valor(row.get("nombre_conductor")),
                limpiar_valor(row.get("tipo_vehiculo")),
                limpiar_valor(row.get("empresa")),
                limpiar_valor(row.get("muelle_descargue")),
                limpiar_valor(row.get("carga_compartida")),
                parse_hora(row.get("hora_ingreso")),
                parse_hora(row.get("hora_salida")),
                limpiar_valor(row.get("actividad_a_desarrollar")),
                limpiar_valor(row.get("dependencia_autoriza")),
                parse_fecha(row.get("fecha_pago_arl")),
                limpiar_valor(row.get("observaciones")),
            ))
        execute_values(self.cur, """
            INSERT INTO proveedores (
                id,fecha,placa_vehiculo,nombre_conductor,tipo_vehiculo,empresa,
                muelle_descargue,carga_compartida,hora_ingreso,hora_salida,
                actividad_a_desarrollar,dependencia_autoriza,fecha_pago_arl,observaciones
            ) VALUES %s
        """, filas)
        self.conn.commit()
        self.totales["proveedores"] = len(filas)
        self.log(f"  → {len(filas)} registros TGN migrados")

    def resumen(self):
        print("\n" + "="*50)
        print("RESUMEN DE MIGRACIÓN")
        print("="*50)
        total = 0
        for tabla, cnt in self.totales.items():
            print(f"  {tabla:<25} {cnt:>6} registros")
            total += cnt
        print(f"  {'TOTAL':<25} {total:>6} registros")
        if self.errores:
            print(f"\n  ERRORES ({len(self.errores)}):")
            for e in self.errores[:10]:
                print(f"    - {e}")
        print("="*50)


def main():
    if not DB_URL:
        print("ERROR: Define DATABASE_URL en el archivo .env")
        sys.exit(1)

    if not CSV_DIR.exists():
        print(f"ERROR: Carpeta {CSV_DIR} no existe. Crea la carpeta y coloca los CSV exportados de Google Sheets.")
        sys.exit(1)

    print("CONTROL VEHICULAR CEDI R10 · Migrador v2")
    print(f"Base de datos: {DB_URL[:40]}...")
    print(f"CSV desde: {CSV_DIR.resolve()}\n")

    m = Migrador(DB_URL)

    # ORDEN CRÍTICO: maestros primero, luego tablas con FK
    ORDEN = [
        ("CONDUCTORES.csv",       m.migrar_conductores),
        ("DISTRIBUCION.csv",      m.migrar_distribucion),
        ("PROVEEDORES BD.csv",    m.migrar_bd_proveedores),
        ("BD_CONTROL ACCESO.csv", m.migrar_bd_control_acceso),
        ("FLOTA PROPIA.csv",      m.migrar_flota),
        ("CONTROL DE ACCESO.csv", m.migrar_control_acceso),
        ("VISITANTES.csv",        m.migrar_visitantes),
        ("PROVEEDORES.csv",       m.migrar_proveedores),
    ]

    for archivo, fn in ORDEN:
        ruta = CSV_DIR / archivo
        if not ruta.exists():
            print(f"  [OMITIDO] {archivo} no encontrado")
            continue
        try:
            df = pd.read_csv(ruta, dtype=str, encoding="utf-8-sig")
            df.columns = [c.strip() for c in df.columns]
            fn(df)
        except Exception as e:
            print(f"  [ERROR] {archivo}: {e}")

    m.resumen()
    m.close()
    print("\nMigración completada.")


if __name__ == "__main__":
    main()
