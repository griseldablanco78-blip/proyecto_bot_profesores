# src/app_streamlit.py
# Versión corregida y mejorada — Tutor IA para Profesores (CABA)
# Reemplazar todo el archivo actual por este contenido.

import streamlit as st
import pandas as pd
import requests
import re
from io import BytesIO
from typing import List, Dict, Any

st.set_page_config(page_title="Tutor IA para Profesores - CABA", layout="wide")

# ---------------------------
# UTILIDADES
# ---------------------------
def to_export_xlsx_url(google_url: str) -> str:
    m = re.search(r"/spreadsheets/d/([^/]+)/", google_url)
    if not m:
        return ""
    doc_id = m.group(1)
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"

@st.cache_data(ttl=3600, show_spinner=False)
def load_all_sheets_from_google(google_url: str) -> Dict[str, pd.DataFrame]:
    """Descarga todas las hojas del Google Sheet y las devuelve en un dict."""
    try:
        export_url = to_export_xlsx_url(google_url)
        r = requests.get(export_url, timeout=30)
        r.raise_for_status()
        xls = pd.ExcelFile(BytesIO(r.content))
        sheets = {}
        for name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=name, engine="openpyxl")
                # normalizar nombres de columnas (strip)
                df.columns = [str(c).strip() for c in df.columns]
                sheets[name] = df
            except Exception as e:
                # no cortamos la carga por una hoja malformada
                st.warning(f"No pude leer la hoja '{name}': {e}")
        return sheets
    except Exception as e:
        st.error(f"No se pudo descargar el Google Sheet: {e}")
        return {}

def split_multi_values(values: List[Any]) -> List[str]:
    """Dado un array de celdas que a veces contienen 'a,b,c', devuelve lista única de items limpios."""
    s = set()
    for v in values:
        if pd.isna(v):
            continue
        txt = str(v)
        # Si tiene separador por coma o punto y coma, separamos
        parts = re.split(r'[;,/|]', txt)
        for p in parts:
            p2 = p.strip()
            if p2:
                s.add(p2)
    return sorted(s)

def find_sheet_by_tokens(sheets: Dict[str, pd.DataFrame], tokens: List[str]) -> str:
    """Busca una hoja cuyo nombre contenga todos los tokens (case-insensitive). Devuelve el primer match."""
    for name in sheets.keys():
        low = name.lower()
        if all(t.lower() in low for t in tokens):
            return name
    return ""

def first_column_name(df: pd.DataFrame) -> str:
    if df is None or df.shape[1] == 0:
        return ""
    return df.columns[0]

def map_codes_from_sheet(df: pd.DataFrame) -> Dict[str, Any]:
    """Mapea primer columna (código) -> fila (serie)."""
    mapping = {}
    if df is None or df.empty:
        return mapping
    key_col = first_column_name(df)
    for _, row in df.iterrows():
        code = row.get(key_col)
        if pd.isna(code):
            continue
        mapping[str(code)] = row
    return mapping

def search_contents_for_subject(subject_name: str,
                                subject_code: str,
                                contenidos_df: pd.DataFrame,
                                related_cols_to_match_code: List[str]) -> List[Dict[str, Any]]:
    """
    Busca en CONTENIDOS_PRODUCIDOS filas relacionadas:
    1) por código (si existe columna que coincida con codes),
    2) o por texto en Titulo/Descripcion.
    Devuelve lista de dicts con Titulo, Descripcion, TipoContenido_Nombre.
    """
    results = []
    if contenidos_df is None or contenidos_df.empty:
        return results

    # intentar por columnas que podrían contener código de relación
    matched_idx = set()
    for col in related_cols_to_match_code:
        if col in contenidos_df.columns:
            # comparar como strings (porque códigos pueden ser numéricos o texto)
            mask = contenidos_df[col].astype(str).str.strip().eq(str(subject_code))
            if mask.any():
                for idx in contenidos_df[mask].index:
                    matched_idx.add(idx)

    # si encontré por código, armar resultados
    for idx in matched_idx:
        row = contenidos_df.loc[idx]
        results.append({
            "Titulo": row.get("Titulo", ""),
            "Descripcion": row.get("Descripcion", ""),
            "TipoContenido_Nombre": row.get("TipoContenido_Nombre", "")
        })

    # si no encontré por código suficiente, buscar por texto (fuzzy simple: contains subject_name)
    if not results:
        txt_cols = []
        for c in ["Titulo", "Descripcion", "TipoContenido_Nombre"]:
            if c in contenidos_df.columns:
                txt_cols.append(c)
        if txt_cols:
            # crear una columna concatenada en lower para búsqueda
            concat = contenidos_df[txt_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
            mask2 = concat.str.contains(subject_name.lower())
            for idx in contenidos_df[mask2].index:
                row = contenidos_df.loc[idx]
                results.append({
                    "Titulo": row.get("Titulo", ""),
                    "Descripcion": row.get("Descripcion", ""),
                    "TipoContenido_Nombre": row.get("TipoContenido_Nombre", "")
                })
    return results

# ---------------------------
# CONFIG Y CARGA
# ---------------------------
st.title("🎓 Tutor IA para Profesores — CABA")
st.write("Seleccioná Modalidad → Año → Nivel → Materia. No mostramos fórmulas ni tablas crudas; el asistente devuelve materiales y contenidos claros.")

# URL fija (la que me pasaste)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1uIMdArE1WHNFDecNlsXW1Pb3hJl_u4HgkFJiFTIxWjk/edit?pli=1&gid=475210533"

with st.spinner("Cargando hojas desde Google Sheets... (puede tardar unos segundos)"):
    sheets = load_all_sheets_from_google(GOOGLE_SHEET_URL)

if not sheets:
    st.stop()

# ---------------------------
# LOCALIZAR HOJAS IMPORTANTES
# ---------------------------
# ESPACIO_CURRICULAR_SA (puede tener varios nombres; lo buscamos por tokens)
espacio_name = find_sheet_by_tokens(sheets, ["espacio", "curricular"])
if not espacio_name:
    # fallback a nombre exacto si existe
    if "ESPACIO_CURRICULAR_SA" in sheets:
        espacio_name = "ESPACIO_CURRICULAR_SA"

espacio_df = sheets.get(espacio_name, pd.DataFrame())

# MODALIDAD: buscar hoja que tenga la columna Modalidad_Tipo o Modalidad_Tipo en cualquier hoja
modalidad_sheet_name = ""
for nm, df in sheets.items():
    if "Modalidad_Tipo" in df.columns or "Modalidad" in df.columns:
        modalidad_sheet_name = nm
        break
modalidad_df = sheets.get(modalidad_sheet_name, pd.DataFrame())

# CONTENIDOS_PRODUCIDOS
contenidos_name = ""
for nm in sheets.keys():
    if "CONTENIDOS_PRODUCIDOS".lower() in nm.lower() or "contenidos" in nm.lower():
        contenidos_name = nm
        break
contenidos_df = sheets.get(contenidos_name, pd.DataFrame())

# DICCIONARIO (descripciones)
dicc_name = ""
for nm in sheets.keys():
    if "diccionario" in nm.lower():
        dicc_name = nm
        break
dicc_df = sheets.get(dicc_name, pd.DataFrame())

# Diagnóstico silencioso (no mostrar tablas completas)
# st.sidebar.write(f"Hojas detectadas: {len(sheets)}")

# ---------------------------
# PREPARAR LISTAS PARA SELECTBOX (normalizando entradas combinadas)
# ---------------------------
# Modalidades: tomar columna Modalidad_Tipo (o Modalidad) de la hoja encontrada
modalidad_col_name = None
if modalidad_df is not None and not modalidad_df.empty:
    if "Modalidad_Tipo" in modalidad_df.columns:
        modalidad_col_name = "Modalidad_Tipo"
    elif "Modalidad" in modalidad_df.columns:
        modalidad_col_name = "Modalidad"
modalidades = []
if modalidad_col_name:
    modalidades = split_multi_values(modalidad_df[modalidad_col_name].astype(str).tolist())

# ESPACIO: columnas para año/nivel y materia
# Busca la columna que contiene 'Año' o 'Nivel' o 'Año/Nivel' y la columna 'Nombre_Espacio_curricular'
anio_col = None
nivel_col = None
materia_col = None
for c in espacio_df.columns:
    c_low = c.lower()
    if any(k in c_low for k in ["año/nivel", "año nivel", "año/niv", "año", "nivel"]) and anio_col is None:
        anio_col = c
    if "nivel" in c_low and nivel_col is None:
        nivel_col = c
    if "nombre_espacio" in c_low or "nombre espacio" in c_low or "nombre esp" in c_low or "espacio curricular" in c_low:
        materia_col = c

# Fallbacks: si no detectó, intentamos nombres comunes
if materia_col is None:
    for candidate in ["Nombre_Espacio_curricular", "Nombre_Espacio", "MateriasAgrupadas", "Materia"]:
        if candidate in espacio_df.columns:
            materia_col = candidate
            break

# Preparar opciones únicas limpias
anios_options = []
if anio_col and anio_col in espacio_df.columns:
    anios_options = split_multi_values(espacio_df[anio_col].dropna().astype(str).tolist())
# Si no hay año, intentar usar nivel_col
if not anios_options and nivel_col and nivel_col in espacio_df.columns:
    anios_options = split_multi_values(espacio_df[nivel_col].dropna().astype(str).tolist())

niveles_options = []
if nivel_col and nivel_col in espacio_df.columns:
    niveles_options = split_multi_values(espacio_df[nivel_col].dropna().astype(str).tolist())
# fallback: si anios_options are numeric 1..6, present as "1er año"...
def normalize_year_label(x):
    x = str(x).strip()
    if x.isdigit():
        return f"{int(x)}º año"
    return x

# materias únicas (cada una en su opción)
materias_options = []
if materia_col and materia_col in espacio_df.columns:
    materias_options = split_multi_values(espacio_df[materia_col].dropna().astype(str).tolist())

# ---------------------------
# UI: Orden Modalidad -> Año -> Nivel -> Materia
# ---------------------------
col_left, col_right = st.columns([1,3])
with col_left:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995574.png", width=140)
    st.markdown("### 👩‍🏫 Asistente Docente")
    st.markdown("Elige: **Modalidad → Año → Nivel → Materia**. El sistema buscará contenidos (CONTENIDOS_PRODUCIDOS) relacionados.")

with col_right:
    st.header("🔎 Búsqueda por filtros")

    # Modalidad
    modalidad_sel = st.selectbox("🏫 Modalidad", ["(Seleccionar)"] + (modalidades if modalidades else ["(no disponible)"]))

    # Año (visual)
    anios_labels = [normalize_year_label(a) for a in anios_options] if anios_options else []
    anio_sel = st.selectbox("📘 Año", ["(Seleccionar)"] + (anios_labels if anios_labels else ["(no disponible)"]))

    # Nivel
    nivel_labels = [f"Nivel {n}" if str(n).isdigit() else str(n) for n in niveles_options] if niveles_options else []
    nivel_sel = st.selectbox("📗 Nivel", ["(Seleccionar)"] + (nivel_labels if nivel_labels else ["(no disponible)"]))

    # Materia
    materia_sel = st.selectbox("📚 Materia", ["(Seleccionar)"] + (materias_options if materias_options else ["(no disponible)"]))

    # Botones
    buscar_btn = st.button("🔍 Buscar materiales y contenidos")
    ayuda_btn = st.button("💡 Pedagogía - Sugerencias rápidas")

# ---------------------------
# LOGICA DE BÚSQUEDA Y MOSTRADO
# ---------------------------
def show_summary_selection():
    st.markdown("### 🔖 Selección")
    st.markdown(f"- **Modalidad:** {modalidad_sel}")
    st.markdown(f"- **Año (visual):** {anio_sel}")
    st.markdown(f"- **Nivel:** {nivel_sel}")
    st.markdown(f"- **Materia:** {materia_sel}")
    st.markdown("---")

if buscar_btn:
    show_summary_selection()

    # intentar relacionar por código si existe
    # primero: obtener map del primer campo (código) de espacio_df
    subject_code = None
    subject_row = None
    if not espacio_df.empty and materia_col in espacio_df.columns:
        # buscamos fila cuyo nombre de materia coincida exactamente
        mask_mat = espacio_df[materia_col].astype(str).str.strip().eq(str(materia_sel).strip())
        if mask_mat.any():
            subject_row = espacio_df[mask_mat].iloc[0]
            keycol = first_column_name(espacio_df)
            subject_code = subject_row.get(keycol)

    resultados_contenidos = []
    # intentar buscar relacion por códigos en CONTENIDOS_PRODUCIDOS
    if contenidos_df is not None and not contenidos_df.empty:
        # detectamos columnas posibles que referencien códigos de espacio (buscamos columnas cuyo nombre contenga 'codigo' o 'id' o el nombre del keycol)
        keycol_name = first_column_name(espacio_df)
        candidate_cols = []
        for c in contenidos_df.columns:
            cl = c.lower()
            if 'codigo' in cl or 'id' in cl or (keycol_name and keycol_name.lower() in cl):
                candidate_cols.append(c)

        # busco por código si existe
        if subject_code is not None and candidate_cols:
            resultados_contenidos = search_contents_for_subject(materia_sel, subject_code, contenidos_df, candidate_cols)

        # fallback: buscar por texto en Titulo o Descripcion
        if not resultados_contenidos:
            resultados_contenidos = search_contents_for_subject(materia_sel, subject_code or "", contenidos_df, [])

    # Mostrar contenidos encontrados
    if resultados_contenidos:
        st.subheader("📖 Contenidos relacionados (CONTENIDOS_PRODUCIDOS)")
        shown = set()
        for r in resultados_contenidos:
            t = r.get("Titulo") or r.get("TipoContenido_Nombre") or "Sin título"
            if t in shown:
                continue
            shown.add(t)
            st.markdown(f"**{t}**")
            desc = r.get("Descripcion")
            tipo = r.get("TipoContenido_Nombre")
            if tipo:
                st.caption(f"Tipo: {tipo}")
            if desc:
                st.write(desc)
            st.markdown("---")
    else:
        st.info("No encontré contenidos relacionados en CONTENIDOS_PRODUCIDOS. Probá otra combinación o usa el botón de ayuda pedagógica.")

    # además, podemos buscar en DICCIONARIO la descripción de la materia si existe
    if dicc_df is not None and not dicc_df.empty:
        # buscar coincidencia por nombre de materia en columna Descripción (o similar)
        desc_candidates = []
        for c in dicc_df.columns:
            if "descrip" in c.lower():
                # tomar filas que contengan el nombre de la materia
                mask = dicc_df[c].astype(str).str.lower().str.contains(materia_sel.lower())
                if mask.any():
                    desc_candidates.extend(dicc_df.loc[mask, c].astype(str).tolist())
        if desc_candidates:
            st.subheader("📝 Descripciones (Diccionario)")
            for d in desc_candidates[:5]:
                st.write(d)
            st.markdown("---")

if ayuda_btn:
    # Sugerencias pedagógicas simples (pueden ampliarse con LLM/OPENAI)
    st.subheader("💡 Sugerencias pedagógicas rápidas")
    if materia_sel and materia_sel != "(Seleccionar)":
        st.markdown(f"- Reforzá contenidos clave de {materia_sel} con ejercicios cortos (10-15 min).")
        st.markdown("- Dividí la clase en: explicación (15'), práctica guiada (20'), práctica autónoma (15').")
        st.markdown("- Si hay estudiantes con rezago en niveles anteriores, prepará fichas de refuerzo con problemas resueltos.")
        st.markdown("- Usá actividades interdisciplinares con otras materias del mismo nivel.")
    else:
        st.info("Seleccioná primero la materia para recibir sugerencias específicas.")

# ---------------------------
# SIDEBAR: AVATAR Y NOTAS
# ---------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995574.png", width=120)
    st.markdown("### 👩‍🏫 Tutor IA — Ayuda")
    st.write("Si la Modalidad no aparece, revisá en qué hoja está la columna `Modalidad_Tipo` (la app la busca automáticamente).")
    st.caption("No mostramos fórmulas ni tablas crudas. Si necesitás ver relación por códigos explícitos, avisame y lo hacemos visualmente.")

# FIN

