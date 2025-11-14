# src/app_streamlit.py
# Tutor IA para Profesores - buscador por modalidad / año(estudiante) / nivel(materia) / materia
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import re
import math
import random

st.set_page_config(page_title="Tutor IA - Secundaria Aprende (CABA)", layout="wide")
st.title("🎓 Tutor IA para Profesores - Secundaria Aprende (CABA)")
st.write("Este asistente busca materiales por modalidad, año del estudiante, nivel de la materia y materia (no muestra hojas completas).")

# -------------------------
# CONFIG: Google Sheet pública (tu URL)
# -------------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1uIMdArE1WHNFDecNlsXW1Pb3hJl_u4HgkFJiFTIxWjk/edit?gid=475210533"

def to_export_xlsx_url(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([^/]+)/", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx" if m else ""

@st.cache_data(ttl=1800, show_spinner=False)
def load_public_sheets(export_url: str):
    try:
        r = requests.get(export_url, timeout=30)
        r.raise_for_status()
        xls = pd.ExcelFile(BytesIO(r.content))
        sheets = {}
        for name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=name, engine="openpyxl")
            # limpiar nombres columnas
            df.columns = [str(c).strip() for c in df.columns]
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error("Error cargando Google Sheet: " + str(e))
        return {}

# -------------------------
# CARGAR SHEETS
# -------------------------
export_url = to_export_xlsx_url(GOOGLE_SHEET_URL)
sheets = load_public_sheets(export_url)

# detectar hoja principal (ESPACIO_CURRICULAR_SA)
espacio_name = None
for name in sheets.keys():
    if "espacio" in name.lower() and "curricular" in name.lower():
        espacio_name = name
        break

if espacio_name is None:
    st.error("No se encontró la hoja ESPACIO_CURRICULAR en el Google Sheet. Revisá el nombre de las hojas.")
    st.stop()

df_ec = sheets[espacio_name].copy()

# -------------------------
# UTILIDADES para detectar columnas robustamente
# -------------------------
def find_col(df, keywords_any=None, keywords_all=None):
    """
    find_col(df, keywords_any=["materia","materias"]) -> first col that contains any keyword
    or keywords_all to require all keywords present in column name.
    """
    for col in df.columns:
        key = col.lower().replace("ó","o").replace("í","i").replace("_"," ").strip()
        if keywords_all:
            if all(k in key for k in keywords_all):
                return col
        if keywords_any:
            if any(k in key for k in keywords_any):
                return col
    return None

# posibles nombres
col_modalidad = find_col(df_ec, keywords_any=["modalidad", "modalidad_tipo", "modalidad tipo", "regimen", "tipo"])
col_yearlevel = find_col(df_ec, keywords_any=["año/nivel", "año nivel", "año", "nivel", "ano/nivel", "año/nivel"])
col_materias = find_col(df_ec, keywords_any=["materias agrupadas", "materiasagrupadas", "materia", "materias", "nombre especialidad", "especialidad"])
# fallback print warnings
missing = []
if not col_modalidad: missing.append("Modalidad_Tipo")
if not col_yearlevel: missing.append("Año/Nivel")
if not col_materias: missing.append("MateriasAgrupadas")
if missing:
    st.warning(f"No se detectaron columnas esperadas: {', '.join(missing)}. Revisa nombres en '{espacio_name}'. Mostrando columnas encontradas:")
    st.write(list(df_ec.columns[:40]))  # breve diagnóstico
# normalize column names access
# we'll use variables col_modalidad, col_yearlevel, col_materias (strings) when available

# -------------------------
# Construir listas para combos
# -------------------------
def unique_sorted_nums(series):
    vals = [v for v in series.dropna().unique().tolist() if str(v).strip()!=""]
    nums = []
    for v in vals:
        try:
            nums.append(int(float(str(v))))
        except Exception:
            # try extract digits
            m = re.search(r"\d+", str(v))
            if m:
                nums.append(int(m.group()))
    return sorted(list(set(nums)))

modalities = sorted(df_ec[col_modalidad].dropna().astype(str).unique().tolist()) if col_modalidad else []
# año/nivel en hoja equivale al nivel (por ej 1..6). Generamos dos vistas:
subject_levels = unique_sorted_nums(df_ec[col_yearlevel]) if col_yearlevel else []
# student years: visual 1º..6º año (se pueden usar libremente; pueden diferir del nivel)
student_years = list(range(1,7))  # mostramos 1..6 siempre porque visualmente queremos eso
subjects = sorted(df_ec[col_materias].dropna().astype(str).unique().tolist()) if col_materias else []

# -------------------------
# SIDEBAR: avatar (solo imagen + diálogo)
# -------------------------
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1995/1995574.png", width=140)
st.sidebar.markdown("### 👩‍🏫 Tu Tutor Docente")
if "help_bubble" not in st.session_state:
    st.session_state.help_bubble = "Seleccioná Modalidad, Año (tu año actual), Nivel (nivel de la materia) y Materia."

st.sidebar.info(st.session_state.help_bubble)

# -------------------------
# INTERFAZ PRINCIPAL: combos
# -------------------------
st.header("🎯 Consulta por Modalidad — Año (estudiante) — Nivel (materia) — Materia")
c1, c2, c3, c4 = st.columns(4)

with c1:
    selected_mod = st.selectbox("Modalidad", ["(todas)"] + modalities, index=0)
with c2:
    sy_label = [f"{y}º año" for y in student_years]
    selected_student_year_label = st.selectbox("Año (estudiante)", ["(no indicar)"] + sy_label, index=0)
    # parse to int or None
    selected_student_year = None
    if selected_student_year_label != "(no indicar)":
        selected_student_year = int(re.search(r"\d+", selected_student_year_label).group())
with c3:
    lvl_label = [f"Nivel {n}" for n in subject_levels] if subject_levels else []
    selected_subject_level_label = st.selectbox("Nivel de la materia", ["(no indicar)"] + lvl_label, index=0)
    selected_subject_level = None
    if selected_subject_level_label != "(no indicar)":
        selected_subject_level = int(re.search(r"\d+", selected_subject_level_label).group())
with c4:
    selected_subject = st.selectbox("Materia", ["(todas)"] + subjects, index=0)

st.markdown("---")

# -------------------------
# BÚSQUEDA: prioridad — buscar materiales para la materia seleccionada en el nivel seleccionado
# -------------------------
def find_material_columns(df):
    keywords = ["material", "recurso", "url", "link", "bibli", "bibliografía", "enlace"]
    cols = [c for c in df.columns if any(k in c.lower() for k in keywords)]
    # si no hay, ofrecer columnas menos específicas (ej: contenidos, descripcion)
    if not cols:
        fallback = [c for c in df.columns if any(k in c.lower() for k in ["contenido", "descripcion", "tema", "unidad"])]
        return fallback[:6]
    return cols

materials_cols = find_material_columns(df_ec)

# apply filters safely
df_filtered = df_ec.copy()
if selected_mod != "(todas)":
    if col_modalidad:
        df_filtered = df_filtered[df_filtered[col_modalidad].astype(str) == selected_mod]
if selected_subject != "(todas)":
    if col_materias:
        df_filtered = df_filtered[df_filtered[col_materias].astype(str) == selected_subject]
if selected_subject_level is not None:
    if col_yearlevel:
        # compare numeric extraction from column
        def extract_level_val(x):
            try:
                return int(float(str(x)))
            except Exception:
                m = re.search(r"\d+", str(x))
                return int(m.group()) if m else None
        df_filtered = df_filtered[df_filtered[col_yearlevel].apply(lambda v: extract_level_val(v) == selected_subject_level)]

# Ahora df_filtered contiene filas que correspondan a la materia y nivel de materia (y modal)
# Mostrar resultados de forma limpia: únicamente columnas de materiales
st.subheader("📦 Materiales / Recursos encontrados (solo lo relevante)")

if df_filtered.empty:
    st.info("No se encontraron materiales exactos para esa combinación.")
    # sugerir alternativas: mismas materia en otros niveles cercanos
    suggestions = []
    if selected_subject != "(todas)":
        # buscar rows con la misma materia pero distinto nivel
        same_subj = df_ec[df_ec[col_materias].astype(str) == selected_subject] if col_materias else pd.DataFrame()
        if not same_subj.empty:
            # obtener niveles disponibles
            avail_levels = unique_sorted_nums(same_subj[col_yearlevel]) if col_yearlevel else []
            if avail_levels:
                suggestions.append(f"La materia '{selected_subject}' está también en niveles: {', '.join(str(v) for v in avail_levels)}.")
                # si student_year > subject_level, sugerir practicar nivel más bajo
                if selected_student_year and selected_subject_level:
                    if selected_student_year > selected_subject_level:
                        suggestions.append("Sugerencia: estás en un año superior al nivel de la materia. El avatar puede proponer actividades de refuerzo para el nivel seleccionado.")
    if not suggestions:
        suggestions = ["Probá buscar la materia sin filtro de nivel para ver todas las coincidencias."]
    for s in suggestions:
        st.info(s)
    # mostrar algunas filas de contexto (solo materias y niveIs) para ayudar a elegir
    help_preview = []
    if selected_subject != "(todas)" and col_materias:
        help_preview = df_ec[df_ec[col_materias].astype(str) == selected_subject][[col_yearlevel, col_materias]].drop_duplicates().head(6)
    elif col_materias:
        help_preview = df_ec[[col_yearlevel, col_materias]].drop_duplicates().head(6)
    if not help_preview.empty:
        st.markdown("Ejemplos (nivel — materia):")
        st.table(help_preview.rename(columns={col_yearlevel:"Nivel (Año/Nivel)", col_materias:"Materia"}))
else:
    # mostrar cada fila encontrada, pero solo columnas materials_cols (si hay), y una vista resumen
    # también mostramos si hay enlace en otra hoja (buscar sheets con 'link' o 'recursos')
    resource_sheets = [n for n in sheets.keys() if "link" in n.lower() or "recurs" in n.lower() or "url" in n.lower()]
    for idx, row in df_filtered.iterrows():
        st.markdown(f"**• Fuente:** {espacio_name} — fila {idx}")
        # summary: modalidad / añoNivel / materia
        summary_parts = []
        if col_modalidad: summary_parts.append(f"Modalidad: **{row[col_modalidad]}**")
        if col_yearlevel: summary_parts.append(f"Nivel (Año/Nivel): **{row[col_yearlevel]}**")
        if col_materias: summary_parts.append(f"Materia: **{row[col_materias]}**")
        st.markdown(" • ".join(summary_parts))
        # materials
        if materials_cols:
            for mc in materials_cols:
                val = row.get(mc, "")
                if pd.notna(val) and str(val).strip()!="":
                    st.markdown(f"- **{mc}**: {str(val)}")
        else:
            # fallback: intentar mostrar columnas de unidad/tema/contenido
            fallback_cols = [c for c in df_ec.columns if any(k in c.lower() for k in ["unidad","tema","contenido","secuencia"])]
            for fc in fallback_cols[:6]:
                v = row.get(fc,"")
                if pd.notna(v) and str(v).strip()!="":
                    st.markdown(f"- **{fc}**: {str(v)}")
        # buscar enlaces relacionados en otras hojas (si existen)
        if resource_sheets:
            for rn in resource_sheets:
                df_r = sheets[rn]
                # intentar encontrar filas por materia exact match or contain
                matches = None
                if col_materias and col_materias in df_r.columns:
                    matches = df_r[df_r[col_materias].astype(str).str.contains(str(row.get(col_materias,"")), case=False, na=False)]
                else:
                    # search any column for subject name
                    matches = df_r[df_r.apply(lambda r_ser: r_ser.astype(str).str.contains(str(row.get(col_materias,"")), case=False, na=False).any(), axis=1)]
                if not matches.empty:
                    st.markdown(f"  - Recursos adicionales en hoja **{rn}**:")
                    # show up to 3 matches with their link-like columns
                    link_cols = [c for c in df_r.columns if any(k in c.lower() for k in ["link","url","enlace"])]
                    show_cols = link_cols or df_r.columns[:4].tolist()
                    for j, rmatch in matches.head(3).iterrows():
                        parts = []
                        for sc in show_cols:
                            v = rmatch.get(sc,"")
                            if pd.notna(v) and str(v).strip()!="":
                                parts.append(f"{sc}: {v}")
                        st.markdown("    - " + " | ".join(parts))
        st.markdown("---")

# -------------------------
# Avatar suggestions / guardar último consejo
# -------------------------
if st.button("Pedir consejo pedagógico (avatar)"):
    # crear un texto corto de sugerencias basadas en la selección
    advice = []
    if selected_subject != "(todas)":
        advice.append(f"Para la materia *{selected_subject}* (Nivel {selected_subject_level if selected_subject_level else '—'}), proponé 3 actividades cortas: 1) práctica guiada, 2) actividad grupal 3) evaluación formativa.")
    else:
        advice.append("Indicá una materia para recibir consejos específicos.")
    # consejos genéricos según diferencia entre año del estudiante y nivel de la materia
    if selected_student_year and selected_subject_level:
        if selected_student_year > selected_subject_level:
            advice.append("Sugerencia: enfocá refuerzo en contenidos previos del nivel seleccionado (recuperación). Usa ejercicios cortos diarios y mapas conceptuales.")
        elif selected_student_year < selected_subject_level:
            advice.append("Sugerencia: adelantá nociones clave y actividades de diagnóstico para identificar brechas antes de avanzar.")
    st.session_state["last_advice"] = "\n\n".join(advice)
    st.success("El avatar generó un consejo pedagógico breve. Está disponible en la burbuja lateral.")

if "last_advice" in st.session_state:
    st.sidebar.markdown("### 💬 Burbuja del avatar")
    st.sidebar.info(st.session_state["last_advice"])

# footer
st.caption("Nota: la app toma los datos del Google Sheet público y muestra solo recursos relevantes (no volca el Excel completo).")

