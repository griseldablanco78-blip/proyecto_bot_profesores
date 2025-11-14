# ------------------------------------------------------------------------
# 🎓 Tutor IA para Profesores - Sistema Educativo CABA
# ------------------------------------------------------------------------
import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import re
import json
import random

# ------------------------------------------------------------------------
# CONFIGURACIÓN INICIAL
# ------------------------------------------------------------------------
st.set_page_config(
    page_title="Tutor IA para Profesores - CABA",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Tutor IA para Profesores - Sistema Educativo CABA")
st.write(
    "Bienvenido/a. Este asistente permite consultar el **ecosistema educativo** de la Ciudad de Buenos Aires y "
    "proporciona sugerencias o materiales según modalidad, año, nivel y materia."
)

# ------------------------------------------------------------------------
# FUNCIÓN: Sanitizar celdas
# ------------------------------------------------------------------------
def sanitize_cell_value(val):
    if isinstance(val, str):
        return val.strip()
    return val

# ------------------------------------------------------------------------
# FUNCIÓN: Convertir URL pública de Google Sheets a XLSX export
# ------------------------------------------------------------------------
def to_export_xlsx_url(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([^/]+)/", url)
    if not m:
        return ""
    doc_id = m.group(1)
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"

# ------------------------------------------------------------------------
# FUNCIÓN: Cargar hoja pública
# ------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def load_public_sheet_as_dict(xlsx_url: str) -> dict:
    try:
        resp = requests.get(xlsx_url, timeout=30)
        resp.raise_for_status()
        xls = pd.ExcelFile(BytesIO(resp.content))
        sheets = {}
        for name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=name)
            df = df.fillna("").map(sanitize_cell_value)
            sheets[name] = df
        return sheets
    except Exception as e:
        st.error(f"Error al cargar Google Sheet: {e}")
        return {}

# ------------------------------------------------------------------------
# CARGA AUTOMÁTICA DESDE GOOGLE SHEET
# ------------------------------------------------------------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1uIMdArE1WHNFDecNlsXW1Pb3hJl_u4HgkFJiFTIxWjk/edit?gid=475210533"
export_url = to_export_xlsx_url(GOOGLE_SHEET_URL)
sheets_dict = load_public_sheet_as_dict(export_url)

# ------------------------------------------------------------------------
# DETECTAR HOJA “Espacio Curricular”
# ------------------------------------------------------------------------
# ------------------ Reemplazar desde aquí: Extracción + combos dependientes ------------------

# detectar la hoja "espacio curricular" (insensible a mayúsc/minúsc)
espacio_df = None
for name, df in sheets_dict.items():
    if "curricular" in name.lower() or "espacio" in name.lower():
        espacio_df = df.copy()
        break

if espacio_df is None:
    st.error("❌ No encontré una hoja que parezca 'Espacio Curricular'. Verificá el Google Sheet.")
    st.stop()

# Normalizar nombres de columnas (map original -> cleaned)
col_map = {}
for col in espacio_df.columns:
    clean = col.lower().strip()
    clean = clean.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    clean = clean.replace(" ", "_")
    col_map[clean] = col  # cleaned -> original

# heurística para localizar columnas importantes
def find_col_by_keywords(*keywords):
    for k,orig in col_map.items():
        if all(kw in k for kw in keywords):
            return orig
    return None

# columnas candidatas (probar varias alternativas)
col_modalidad = find_col_by_keywords("modalidad") or find_col_by_keywords("modalidad_tipo") or find_col_by_keywords("modalidad", "tipo")
col_nombre = find_col_by_keywords("nombre", "especialidad") or find_col_by_keywords("nombre_espacio") or find_col_by_keywords("nombre")
# 'año' puede aparecer como "año/nivel" o "año" o "anio"
col_ano_nivel = find_col_by_keywords("anno") or find_col_by_keywords("año") or find_col_by_keywords("anio") or find_col_by_keywords("ano_nivel") or find_col_by_keywords("ano")
# 'nivel' a veces está incluido en la misma columna (ej "Nivel 1") o en columna "Nivel"
col_nivel = find_col_by_keywords("nivel") or find_col_by_keywords("nivel_de_cursada") or find_col_by_keywords("nivel", "curso")

# fallback: si no encontramos columnas asume nombres comunes
if not col_modalidad and "Modalidad_Tipo" in espacio_df.columns:
    col_modalidad = "Modalidad_Tipo"
if not col_nombre and "Nombre_Espacio_curricular" in espacio_df.columns:
    col_nombre = "Nombre_Espacio_curricular"

# sanitizar dataframe: quitar fórmulas y NaN
def sanitize_df(df):
    df2 = df.fillna("")
    for c in df2.columns:
        # convertir todo a string para búsqueda (pero mantenemos original en row display)
        df2[c] = df2[c].astype(str).apply(lambda v: "" if v.strip().startswith("=") else v.strip())
    return df2

espacio_df = sanitize_df(espacio_df)

# EXTRAER valores para los combos (con orden y formato bonito)
# Modalidades
modalities = sorted([m for m in espacio_df[col_modalidad].unique() if m]) if col_modalidad else []

# Años: intentar extraer números 1..6 desde col_ano_nivel o desde texto que contenga 'Nivel X'
years = set()
if col_ano_nivel:
    for v in espacio_df[col_ano_nivel].unique():
        txt = str(v)
        m = re.search(r"\b([1-6])\b", txt)
        if m:
            years.add(int(m.group(1)))
# si no hay, intentar buscar 'Nivel' en otras columnas
if not years and col_nivel:
    for v in espacio_df[col_nivel].unique():
        txt = str(v)
        m = re.search(r"\b([1-6])\b", txt)
        if m:
            years.add(int(m.group(1)))
# formato para mostrar: "1er año", "2do año", ...
years = sorted(list(years))
years_display = [f"{y}º año" for y in years] if years else []

# Niveles: extraer "Nivel X" o convertir números a Nivel X
levels = set()
if col_nivel:
    for v in espacio_df[col_nivel].unique():
        txt = str(v)
        m = re.search(r"\b([1-6])\b", txt)
        if m:
            levels.add(int(m.group(1)))
# convertir a lista ordenada
levels = sorted(list(levels))
levels_display = [f"Nivel {l}" for l in levels] if levels else []

# Materias (Nombre de especialidad curricular)
subjects = sorted([s for s in espacio_df[col_nombre].unique() if s]) if col_nombre else []

# si algún listado quedó vacío, rellenar con un placeholder razonable
if not modalities: modalities = ["(no disponible)"]
if not years_display: years_display = ["(no disponible)"]
if not levels_display: levels_display = ["(no disponible)"]
if not subjects: subjects = ["(no disponible)"]

# ---------------- UI: 4 combos dependientes ----------------
st.subheader("🎓 Consulta por modalidad, nivel, año y materia")

c1, c2, c3, c4 = st.columns(4)
with c1:
    selected_modalidad = st.selectbox("Modalidad", options=modalities, index=0, key="sel_modalidad")
with c2:
    selected_year = st.selectbox("Año (ej: 1º año)", options=years_display, index=0, key="sel_ano")
with c3:
    selected_level = st.selectbox("Nivel (ej: Nivel 1)", options=levels_display, index=0, key="sel_nivel")
with c4:
    selected_subject = st.selectbox("Materia (especialidad)", options=subjects, index=0, key="sel_materia")

# ---------------- Filtrado tolerante (contains en vez de == para robustez) ----------------
# convertir seleccion a comparables
def normalize(v): 
    return str(v).strip().lower()

sel_mod = normalize(selected_modalidad)
sel_year_num = None
m = re.search(r"(\d+)", selected_year or "")
if m:
    sel_year_num = m.group(1)
sel_level_num = None
m2 = re.search(r"(\d+)", selected_level or "")
if m2:
    sel_level_num = m2.group(1)
sel_subject = normalize(selected_subject)

results = []
for idx, row in espacio_df.iterrows():
    # combinar campos como texto para búsqueda tolerante
    row_text = " ".join([str(row.get(c, "")).lower() for c in espacio_df.columns])
    ok = True
    if sel_mod and sel_mod != "(no disponible)" and sel_mod not in row_text:
        ok = False
    if sel_year_num:
        if sel_year_num not in row_text:
            ok = False
    if sel_level_num:
        if sel_level_num not in row_text:
            ok = False
    if sel_subject and sel_subject != "(no disponible)" and sel_subject not in row_text:
        ok = False
    if ok:
        results.append((idx, row))

# mostrar resultados
if not results:
    st.warning("No encontré resultados exactos. Probá con menos filtros o revisá la selección.")
    # ofrecer sugerencias automáticas (palabras clave) si hay al menos algo
    # extraer keywords simples de la columna de materias
    if subjects and subjects[0] != "(no disponible)":
        st.info("Sugerencia rápida: probá con estas materias relacionadas:")
        st.write(", ".join(subjects[:6]))
else:
    st.success(f"Encontré {len(results)} filas que coinciden. Mostrando top 10:")
    for i, (rid, rrow) in enumerate(results[:10], start=1):
        st.markdown(f"**[{i}]** Sheet: Espacio Curricular — fila {rid}")
        # mostrar versión limpia (sin fórmulas) y corta
        display_text = []
        for c in espacio_df.columns:
            val = rrow[c]
            if val and not str(val).strip().startswith("="):
                display_text.append(f"**{c}**: {val}")
        st.write("  \n".join(display_text[:10]))
        st.markdown("---")

# -------------- Ejemplo de 'JOIN' simple: buscar el ID en otras hojas --------------
# identificar columna ID (ej: ID_Espacio_curricular o Codigo_Espacio_curricular)
id_col = find_col_by_keywords("id", "espacio") or find_col_by_keywords("codigo", "espacio") or \
         find_col_by_keywords("id_espacio") or (espacio_df.columns[0] if len(espacio_df.columns)>0 else None)

if results and id_col:
    # toma primer resultado y busca referencias en otras hojas
    idx0, row0 = results[0]
    id_val = row0.get(id_col, "")
    if id_val:
        related = {}
        for sheet_name, df_other in sheets_dict.items():
            if df_other is espacio_df:
                continue
            # buscar id_val en cualquier columna del sheet (quick scan)
            mask_any = df_other.apply(lambda col: col.astype(str).str.contains(str(id_val), na=False)).any(axis=1)
            hits = df_other[mask_any]
            if not hits.empty:
                related[sheet_name] = hits.head(5)
        if related:
            st.subheader("Registros relacionados (buscando ID en otras hojas)")
            for sname, dfhits in related.items():
                st.markdown(f"**{sname}** — {len(dfhits)} coincidencias (muestra 5)")
                st.dataframe(dfhits)
# ------------------ fin del bloque reemplazado ------------------

# ------------------------------------------------------------------------
# EXTRAER COLUMNAS RELEVANTES
# ------------------------------------------------------------------------
def find_column(df, keywords):
    for col in df.columns:
        text = col.lower().replace("ó", "o").replace("í", "i")
        if all(k in text for k in keywords):
            return col
    return None

col_mod = find_column(espacio_df, ["modalidad"])
col_year = find_column(espacio_df, ["año"])
col_level = find_column(espacio_df, ["nivel"])
col_subject = find_column(espacio_df, ["especialidad", "nombre"])

modalities = sorted(espacio_df[col_mod].unique()) if col_mod else []
years = sorted(espacio_df[col_year].unique()) if col_year else []
levels = sorted(espacio_df[col_level].unique()) if col_level else []
subjects = sorted(espacio_df[col_subject].unique()) if col_subject else []

# ------------------------------------------------------------------------
# SIDEBAR: Avatar
# ------------------------------------------------------------------------
st.sidebar.markdown("### 👩‍🏫 Asistente IA")
avatar_options = {
    "Profesora": "https://cdn-icons-png.flaticon.com/512/194/194938.png",
    "Profesor": "https://cdn-icons-png.flaticon.com/512/4140/4140048.png",
    "Robot Tutor": "https://cdn-icons-png.flaticon.com/512/4712/4712035.png",
}
avatar_choice = st.sidebar.selectbox("Elegí tu avatar:", list(avatar_options.keys()))
st.sidebar.image(avatar_options[avatar_choice], width=150)

# ------------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# ------------------------------------------------------------------------
st.subheader("🎓 Consulta por modalidad, nivel, año y materia")

if not modalities:
    st.warning("⚠️ No se detectó la columna 'Modalidad_Tipo'. Verificá la hoja 'Espacio Curricular'.")

col1, col2, col3, col4 = st.columns(4)

with col1:
    selected_modality = st.selectbox("Modalidad", modalities)
with col2:
    selected_year = st.selectbox("Año", [f"{int(y)}° año" if str(y).isdigit() else y for y in years])
with col3:
    selected_level = st.selectbox("Nivel", [f"Nivel {int(l)}" if str(l).isdigit() else l for l in levels])
with col4:
    selected_subject = st.selectbox("Materia", subjects)

# ------------------------------------------------------------------------
# FILTRAR RESULTADOS
# ------------------------------------------------------------------------

import difflib

# 1) localizar la hoja 'Espacio Curricular' (fuzzy)
espacio_df = None
for name in sheets_dict.keys():
    if "espacio" in name.lower() or "curricular" in name.lower():
        espacio_df = sheets_dict[name]
        break

if espacio_df is None:
    st.error("❌ No se encontró la hoja 'Espacio Curricular' en el Google Sheet. Revisá el nombre de la hoja.")
    st.stop()

# 2) sanitizar dataframe (por columnas para evitar applymap warning)
def sanitize_col_series(s: pd.Series) -> pd.Series:
    try:
        return s.fillna("").astype(str).map(lambda v: "" if (isinstance(v, str) and v.strip().startswith("=")) else v.strip())
    except Exception:
        return s.fillna("").astype(str)

espacio_df = espacio_df.copy()
for col in espacio_df.columns:
    espacio_df[col] = sanitize_col_series(espacio_df[col])

# 3) función para encontrar la mejor columna usando keywords y fuzzy match
def find_best_column(df: pd.DataFrame, candidate_keywords, cutoff=0.5):
    # 1) nombres exactos que contengan todas las keywords
    for col in df.columns:
        name = col.lower().replace("ó", "o").replace("í", "i")
        if all(k in name for k in candidate_keywords):
            return col
    # 2) fuzzy match usando difflib
    cols = [c for c in df.columns]
    joined = " ".join(cols).lower()
    # build list of potential names based on containing any keyword
    potentials = [c for c in cols if any(k in c.lower() for k in candidate_keywords)]
    if potentials:
        # choose best by closeness to the joined keywords string
        best = difflib.get_close_matches(" ".join(candidate_keywords), potentials, n=1, cutoff=cutoff)
        if best:
            return best[0]
    # 3) fallback: try columns that contain any one of the keywords
    for col in df.columns:
        if any(k in col.lower() for k in candidate_keywords):
            return col
    return None

# 4) detectar columnas (intentos con keywords comunes)
col_mod = find_best_column(espacio_df, ["modalidad", "tipo", "regimen"])
col_year = find_best_column(espacio_df, ["año", "anio", "year", "curso"])
col_level = find_best_column(espacio_df, ["nivel", "etapa"])
col_subject = find_best_column(espacio_df, ["especialidad", "nombre", "materia", "asignatura"])

# 5) Informar (sidebar limpio: lo mostramos de forma sutil)
st.sidebar.markdown("### Archivo conectado")
detected = []
if col_mod: detected.append(f"Modalidad → `{col_mod}`")
if col_year: detected.append(f"Año → `{col_year}`")
if col_level: detected.append(f"Nivel → `{col_level}`")
if col_subject: detected.append(f"Materia → `{col_subject}`")
if detected:
    st.sidebar.write("Columnas detectadas: " + " · ".join(detected))
else:
    st.sidebar.write("Columnas detectadas: (ninguna, revisá la hoja)")

# 6) función helper para formatear año/level display
def fmt_year_label(y):
    try:
        yint = int(str(y).strip())
        return f"{yint}° año"
    except Exception:
        return str(y)

def fmt_level_label(l):
    try:
        lint = int(str(l).strip())
        return f"Nivel {lint}"
    except Exception:
        return str(l)

# 7) construir opciones iniciales (no filtradas)
modalities_all = sorted(espacio_df[col_mod].dropna().unique().astype(str).tolist()) if col_mod else []
years_all = sorted(espacio_df[col_year].dropna().unique().tolist()) if col_year else []
levels_all = sorted(espacio_df[col_level].dropna().unique().tolist()) if col_level else []
subjects_all = sorted(espacio_df[col_subject].dropna().unique().astype(str).tolist()) if col_subject else []

# 8) Selectboxes dependientes usando session_state para evitar flicker
if "sel_modality" not in st.session_state:
    st.session_state.sel_modality = modalities_all[0] if modalities_all else ""
if "sel_year" not in st.session_state:
    st.session_state.sel_year = fmt_year_label(years_all[0]) if years_all else ""
if "sel_level" not in st.session_state:
    st.session_state.sel_level = fmt_level_label(levels_all[0]) if levels_all else ""
if "sel_subject" not in st.session_state:
    st.session_state.sel_subject = subjects_all[0] if subjects_all else ""

st.header("🎓 Tutor IA — Consulta por modalidad, año, nivel y materia")
cols = st.columns(4)

with cols[0]:
    selected_modality = st.selectbox("Modalidad", ["(todas)"] + modalities_all, index=0 if st.session_state.sel_modality=="" else (["(todas)"]+modalities_all).index(st.session_state.sel_modality) if st.session_state.sel_modality in modalities_all else 0, key="ui_modality")

with cols[1]:
    # si se eligió modalidad, filtrar años disponibles para esa modalidad
    if selected_modality != "(todas)" and col_mod:
        years_filtered = sorted(espacio_df[espacio_df[col_mod]==selected_modality][col_year].dropna().unique().tolist())
    else:
        years_filtered = years_all.copy()
    years_labels = [fmt_year_label(y) for y in years_filtered]
    selected_year = st.selectbox("Año", ["(todos)"] + years_labels, index=0, key="ui_year")

with cols[2]:
    # filtrar niveles según modalidad + año
    df_tmp = espacio_df.copy()
    if selected_modality != "(todas)" and col_mod:
        df_tmp = df_tmp[df_tmp[col_mod]==selected_modality]
    if selected_year and selected_year != "(todos)" and col_year:
        # quitar sufijo "° año" para comparar (intenta)
        try:
            year_val = int(selected_year.split("°")[0])
            df_tmp = df_tmp[df_tmp[col_year].astype(str).str.contains(str(year_val))]
        except Exception:
            df_tmp = df_tmp[df_tmp[col_year].astype(str).str.contains(selected_year.split()[0])]
    levels_filtered = sorted(df_tmp[col_level].dropna().unique().tolist()) if col_level else []
    level_labels = [fmt_level_label(l) for l in levels_filtered]
    selected_level = st.selectbox("Nivel", ["(todos)"] + level_labels, index=0, key="ui_level")

with cols[3]:
    # filtrar subjects según prev filtros
    df_tmp2 = espacio_df.copy()
    if selected_modality != "(todas)" and col_mod:
        df_tmp2 = df_tmp2[df_tmp2[col_mod]==selected_modality]
    if selected_year and selected_year != "(todos)" and col_year:
        try:
            year_val = int(selected_year.split("°")[0])
            df_tmp2 = df_tmp2[df_tmp2[col_year].astype(str).str.contains(str(year_val))]
        except Exception:
            pass
    if selected_level and selected_level != "(todos)" and col_level:
        try:
            lvl_val = int(selected_level.replace("Nivel ",""))
            df_tmp2 = df_tmp2[df_tmp2[col_level].astype(str).str.contains(str(lvl_val))]
        except Exception:
            pass
    subjects_filtered = sorted(df_tmp2[col_subject].dropna().unique().astype(str).tolist()) if col_subject else []
    selected_subject = st.selectbox("Materia", ["(todas)"] + subjects_filtered, index=0, key="ui_subject")

# 9) Botón de búsqueda y resultados
query = st.text_input("Tu consulta (opcional): usa palabras clave para filtrar materiales o contenidos", value="", key="ui_query")
if st.button("Buscar contenidos y sugerencias"):
    df_search = espacio_df.copy()
    if selected_modality != "(todas)" and col_mod:
        df_search = df_search[df_search[col_mod]==selected_modality]
    if selected_year and selected_year != "(todos)" and col_year:
        try:
            year_val = int(selected_year.split("°")[0])
            df_search = df_search[df_search[col_year].astype(str).str.contains(str(year_val))]
        except Exception:
            pass
    if selected_level and selected_level != "(todos)" and col_level:
        try:
            lvl_val = int(selected_level.replace("Nivel ",""))
            df_search = df_search[df_search[col_level].astype(str).str.contains(str(lvl_val))]
        except Exception:
            pass
    if selected_subject and selected_subject != "(todas)" and col_subject:
        df_search = df_search[df_search[col_subject].astype(str)==selected_subject]

    # si hay query de texto, aplicamos filtro por palabra clave simple
    if query and query.strip():
        q = query.lower().strip()
        mask = df_search.apply(lambda row: row.astype(str).str.lower().str.contains(q).any(), axis=1)
        df_search = df_search[mask]

    if df_search.empty:
        st.warning("No encontré coincidencias exactas para esos filtros. Probá disminuir filtros o usar otra palabra clave.")
        # sugerir keywords
        sample = espacio_df.sample(n=min(3, len(espacio_df))) if len(espacio_df)>0 else None
        if sample is not None:
            suggested = []
            for _, r in sample.iterrows():
                if col_subject: suggested.append(str(r.get(col_subject,"")))
            suggested = [s for s in suggested if s]
            if suggested:
                st.info("💡 Sugerencia: probá con alguna de estas materias: " + ", ".join(suggested[:3]))
    else:
        st.success(f"Encontré {len(df_search)} filas relevantes. Mostrando hasta 50:")
        # mostramos versión limpia (sin fórmulas, truncada)
        def row_preview(r):
            parts=[]
            for c in df_search.columns:
                v = r[c]
                if v is None or str(v).strip()=="":
                    continue
                s = str(v)
                if s.strip().startswith("="): continue
                parts.append(f"{c}: {s}")
            return " | ".join(parts)[:1000]
        previews = [row_preview(r) for _, r in df_search.head(50).iterrows()]
        for i, p in enumerate(previews, start=1):
            st.markdown(f"**[{i}]** {p}")
        # ofrecer ver dataframe completo (limitado)
        if st.checkbox("Ver tabla filtrada (hasta 200 filas)"):
            st.dataframe(df_search.head(200))

# ------------------ FIN BLOQUE --------------------------------------------------


# ------------------------------------------------------------------------
# GLOBITO DE DIÁLOGO DEL AVATAR
# ------------------------------------------------------------------------
if random.random() < 0.3:
    bubbles = [
        "👩‍🏫 Consejo: Si no recordás la materia exacta, escribí solo una palabra clave.",
        "💬 Tip: Podés combinar modalidades con niveles diferentes (como en la nueva secundaria).",
        "📘 ¿Querés materiales actualizados? Visitá el portal *IA Secundaria Aprende GCBA*.",
    ]
    st.sidebar.markdown(f"💬 {random.choice(bubbles)}")
