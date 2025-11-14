# src/app_streamlit.py
# Versión corregida: combos funcionales (Modalidad, Año escolar, Nivel de materia, Materia)
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import re
import random

# ---------------------- Config ----------------------
st.set_page_config(page_title="Tutor IA para Profesores - CABA", layout="wide")
st.title("🎓 Tutor IA para Profesores - Sistema Educativo CABA")
st.write("Consulta por modalidad, año escolar, nivel de la materia y materia. El avatar puede sugerir contenidos para ponerse al día.")

# ---------------------- Helpers ----------------------
def to_export_xlsx_url(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([^/]+)/", url)
    if not m:
        return ""
    doc_id = m.group(1)
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"

@st.cache_data(ttl=3600, show_spinner=False)
def load_public_sheet_as_dict(xlsx_url: str) -> dict:
    try:
        resp = requests.get(xlsx_url, timeout=30)
        resp.raise_for_status()
        xls = pd.ExcelFile(BytesIO(resp.content))
        sheets = {}
        for name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=name, engine="openpyxl")
            # convertir a string y ocultar fórmulas (celdas que empiezan con '=')
            df = df.fillna("").astype(str)
            df = df.apply(lambda s: s.map(lambda v: "" if isinstance(v, str) and v.strip().startswith("=") else v))
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error(f"❌ Error al cargar Google Sheet: {e}")
        return {}

def find_column_by_candidates(df, candidates):
    """Devuelve el nombre de la columna que contenga alguna de las palabras de candidates (insensible a mayúsculas)."""
    for col in df.columns:
        col_norm = col.lower().replace(" ", "").replace("_","")
        for cand in candidates:
            if cand.lower().replace(" ", "").replace("_","") in col_norm:
                return col
    return None

def format_year_label(v):
    try:
        vi = int(float(v))
        return f"{vi}º año"
    except Exception:
        return str(v)

def format_level_label(v):
    try:
        vi = int(float(v))
        return f"Nivel {vi}"
    except Exception:
        return str(v)

# ---------------------- Configuración de sheet URL ----------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1uIMdArE1WHNFDecNlsXW1Pb3hJl_u4HgkFJiFTIxWjk/edit?gid=475210533"
export_url = to_export_xlsx_url(GOOGLE_SHEET_URL)
sheets = load_public_sheet_as_dict(export_url)
if not sheets:
    st.stop()

# ---------------------- Detectar hoja ESPACIO_CURRICULAR_SA (flexible) ----------------------
hoja_ec = None
for name in sheets.keys():
    if "espacio" in name.lower() and "curricular" in name.lower():
        hoja_ec = name
        break
# si no encontró exactamente con esos tokens, permitimos búsqueda por "espacio" o "curricular"
if not hoja_ec:
    for name in sheets.keys():
        if "espacio" in name.lower() or "curricular" in name.lower():
            hoja_ec = name
            break

if not hoja_ec:
    st.error("❌ No se encontró la hoja 'ESPACIO_CURRICULAR_SA' ni variantes en el Google Sheet.")
    st.stop()

df_ec = sheets[hoja_ec].copy()
df_ec.columns = df_ec.columns.str.strip()

# ---------------------- Detectar columnas relevantes (flexible) ----------------------
# candidatos para cada campo (variaciones posibles)
candidates_modalidad = ["modalidad", "modalidad_tipo", "modalidad tipo"]
candidates_year_level = ["año/nivel", "año / nivel", "año", "año nivel", "anios", "anio"]
candidates_level = ["nivel", "nivel de cursada"]
candidates_materia = ["materiasagrupadas", "materias agrupadas", "materia", "materias", "nombreespecialidad", "nombre de especialidad"]

col_modalidad = find_column_by_candidates(df_ec, candidates_modalidad)
# prefer specific Año/Nivel column, sino Año o Nivel
col_aonivel = None
for cand in ["año/nivel", "año / nivel", "año_nivel", "aonivel"]:
    found = find_column_by_candidates(df_ec, [cand])
    if found:
        col_aonivel = found
        break
if not col_aonivel:
    # fallback: try separate año or nivel
    col_aonivel = find_column_by_candidates(df_ec, ["año", "anio", "year"]) or find_column_by_candidates(df_ec, ["nivel"])

# nivel columna (si existe separada)
col_nivel = find_column_by_candidates(df_ec, candidates_level)
# materia
col_materia = find_column_by_candidates(df_ec, candidates_materia)

# avisos si falta algo
if not col_modalidad:
    st.warning("⚠️ No se detectó columna de Modalidad automáticamente.")
if not col_aonivel:
    st.warning("⚠️ No se detectó columna 'Año/Nivel' (busca 'Año' o 'Nivel').")
if not col_materia:
    st.warning("⚠️ No se detectó columna de Materia ('MateriasAgrupadas' o similar).")

# ---------------------- Preparar listas para combos ----------------------
# Modalidad (si no existe, dejamos lista vacía)
modalidades = sorted(df_ec[col_modalidad].dropna().unique().tolist()) if col_modalidad else []
# Materias
materias = sorted(df_ec[col_materia].dropna().unique().tolist()) if col_materia else []

# Para mostrar años y niveles como listas 1..6 si no se detecta el rango real:
# si col_aonivel es numérico en sheet, lo usamos; si no, mostramos 1..6 por defecto
years_raw = []
if col_aonivel:
    # extraer valores que sean dígitos o números
    vals = df_ec[col_aonivel].dropna().unique().tolist()
    # intentar convertir a int si posible
    for v in vals:
        try:
            years_raw.append(int(float(v)))
        except Exception:
            # si no convertible, ignorar
            pass
years_raw = sorted(list(set(years_raw)))
if not years_raw:
    # default 1..6
    years_raw = list(range(1,7))

# niveles (usamos los mismos valores de years_raw como niveles de materia si no hay campo separado)
levels_raw = []
if col_nivel and col_nivel in df_ec.columns:
    vals = df_ec[col_nivel].dropna().unique().tolist()
    for v in vals:
        try:
            levels_raw.append(int(float(v)))
        except Exception:
            pass
levels_raw = sorted(list(set(levels_raw)))
if not levels_raw:
    levels_raw = years_raw.copy()

# ---------------------- Interfaz: combos (orden solicitado) ----------------------
st.subheader("🎯 Seleccioná filtros")

c1, c2, c3, c4 = st.columns(4)

with c1:
    modalidad_sel = st.selectbox("🏫 Modalidad", options=modalidades if modalidades else ["(no disponible)"])
with c2:
    # Año escolar del docente/alumno (contexto) — mostramos labels bonitos
    año_choices = [format_year_label(y) for y in years_raw]
    año_sel = st.selectbox("📘 Año escolar (tu año)", options=año_choices)
with c3:
    nivel_choices = [format_level_label(n) for n in levels_raw]
    nivel_sel = st.selectbox("📗 Nivel de la materia (curricular)", options=nivel_choices)
with c4:
    materia_sel = st.selectbox("📚 Materia", options=materias if materias else ["(no disponible)"])

# ---------------------- Filtrado: importante -> el nivel de la materia es el que buscamos en la hoja ----------------------
st.markdown("---")
st.subheader("🔎 Resultados")

# build filter robustamente: si columnas faltan, avisar y no romper
try:
    # convierto los labels de nivel/ano a integers para comparar con valores en sheet
    def parse_label_to_int(lbl):
        if lbl is None:
            return None
        m = re.search(r"(\d+)", str(lbl))
        return int(m.group(1)) if m else None

    nivel_int = parse_label_to_int(nivel_sel)
    año_int = parse_label_to_int(año_sel)

    # condición base True
    mask = pd.Series([True] * len(df_ec), index=df_ec.index)

    if col_modalidad:
        mask = mask & (df_ec[col_modalidad].astype(str) == str(modalidad_sel))

    # Si la hoja tiene columna específica de nivel (col_nivel), la usamos; si no, usamos col_aonivel
    if col_nivel and col_nivel in df_ec.columns:
        # comparar con nivel_int (si no es convertible, comparamos string)
        try:
            mask = mask & (df_ec[col_nivel].astype(float).fillna(-1).astype(int) == nivel_int)
        except Exception:
            mask = mask & (df_ec[col_nivel].astype(str) == str(nivel_int))
    elif col_aonivel and col_aonivel in df_ec.columns:
        try:
            mask = mask & (df_ec[col_aonivel].astype(float).fillna(-1).astype(int) == nivel_int)
        except Exception:
            mask = mask & (df_ec[col_aonivel].astype(str) == str(nivel_int))

    if col_materia:
        mask = mask & (df_ec[col_materia].astype(str) == str(materia_sel))

    resultado = df_ec[mask].copy()
except Exception as e:
    st.error(f"Error aplicando filtros: {e}")
    resultado = pd.DataFrame()

# ---------------------- Mostrar resultado limpio (solo recursos) ----------------------
if resultado.empty:
    st.info("No se encontraron filas que coincidan exactamente. El avatar puede sugerir ejercicios y contenidos para ponerse al día.")
    # sugerencia automática basada en materia/nivel
    if materia_sel and materia_sel != "(no disponible)":
        st.info(f"💡 Sugerencia del avatar: para **{materia_sel} (Nivel {nivel_int})**, probá con ejercicios de práctica focalizados en: operaciones básicas, resolución de problemas y lectura comprensiva (según corresponda).")
else:
    # buscamos columnas que parezcan contener materiales/recursos/links
    cols_materiales = [c for c in resultado.columns if any(k in c.lower() for k in ["material", "recurso", "url", "link", "bibliograf", "bibliografía"])]
    if not cols_materiales:
        # fallback: mostrar un resumen muy limpio con columnas clave (sin fórmulas)
        cols_show = [c for c in resultado.columns if c.lower() in ["unidad", "tema", "contenido", "descripcion", "descripcion general", "sintesis"]]
        if not cols_show:
            # si tampoco hay columnas amigables, mostramos mensaje que hay datos pero sin detallar
            st.success(f"Se encontraron {len(resultado)} registros relevantes para {materia_sel} (Nivel {nivel_int}).")
            st.info("Hay datos asociados en la planilla. Puedo guardar o generar sugerencias si querés.")
        else:
            st.success(f"Se encontraron {len(resultado)} registros. Mostrando resumen:")
            for idx, row in resultado[cols_show].iterrows():
                parts = []
                for c in cols_show:
                    v = str(row[c]).strip()
                    if v:
                        parts.append(f"**{c}**: {v}")
                st.markdown(" • " + " — ".join(parts))
    else:
        st.success(f"Se encontraron {len(resultado)} registros. Materiales:")
        for idx, row in resultado[cols_materiales].iterrows():
            for c in cols_materiales:
                v = str(row[c]).strip()
                if v:
                    st.markdown(f"- **{c}**: {v}")

# ---------------------- Sidebar (avatar docente + globito) ----------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995574.png", width=140)
    st.markdown("### 👩‍🏫 Tu Tutor Docente")
    st.caption(f"Conectado a: **{hoja_ec}**")
    # Globito dependiente del contexto
    tip_pool = [
        "Si estás atrasado/a en una materia, pedí actividades de recuperación por nivel.",
        "Recordá: el 'Año escolar' es tu curso actual; el 'Nivel de la materia' es lo que indica el programa.",
        "Si no aparece material, el avatar puede sugerir una secuencia de 3 clases para recuperar contenidos."
    ]
    # mostrar consejo contextualizado
    if materia_sel and materia_sel != "(no disponible)":
        st.info(f"💬 {random.choice(tip_pool)}")
    else:
        st.info("💬 Seleccioná una modalidad y materia para obtener sugerencias más precisas.")

# ---------------------- FIN ----------------------
