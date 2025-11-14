# src/app_streamlit.py
# Tutor IA para Profesores - versión lista para pegar
# Reemplazar totalmente el archivo actual por este.

import os
import re
import json
import requests
import pandas as pd
from io import BytesIO
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Tutor IA para Profesores", layout="wide")

# ---------------------------
# Config: URL pública del Google Sheet (modificá si necesitás otra)
# ---------------------------
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1uIMdArE1WHNFDecNlsXW1Pb3hJl_u4HgkFJiFTIxWjk/edit?gid=475210533"

# ---------------------------
# Utilidades
# ---------------------------
@st.cache_data(ttl=3600)
def load_public_sheet_dict(sheet_url: str) -> dict:
    """Descarga el Google Sheet como xlsx y lo devuelve como dict(name -> DataFrame)."""
    try:
        m = re.search(r"/spreadsheets/d/([^/]+)", sheet_url)
        if not m:
            return {}
        file_id = m.group(1)
        export_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        r = requests.get(export_url, timeout=30)
        r.raise_for_status()
        xls = pd.ExcelFile(BytesIO(r.content))
        sheets = {}
        for name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=name, engine="openpyxl")
                # limpiar nombres de columnas
                df.columns = [str(c).strip() for c in df.columns]
                sheets[name] = df
            except Exception:
                continue
        return sheets
    except Exception as e:
        # no usamos st.error aquí para evitar que se muestre en caché antes de layout
        return {}

def short_text(txt, n=300):
    t = str(txt)
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0] + "…"

def extract_unique_subjects(df, candidates):
    """Extrae valores únicos de columnas de materia, separando por comas/puntos y comas."""
    vals = []
    if df is None or df.empty:
        return []
    for col in candidates:
        if not col or col not in df.columns:
            continue
        series = df[col].dropna().astype(str)
        for v in series:
            parts = re.split(r"\s*[,;]\s*", v)
            for p in parts:
                p_clean = p.strip()
                if p_clean:
                    vals.append(p_clean)
    # preservar orden y eliminar duplicados
    unique = list(dict.fromkeys(vals))
    # opcional: ordenar alfabéticamente para el select
    unique_sorted = sorted(unique, key=lambda x: x.lower())
    return unique_sorted

def find_link_column(df_from, df_to):
    """
    Busca una columna en df_to que comparta valores con la primera columna de df_from.
    Retorna nombre de columna o None.
    """
    if df_from is None or df_from.empty or df_to is None or df_to.empty:
        return None
    key_col = df_from.columns[0]
    vals = set(df_from[key_col].dropna().astype(str).unique())
    for col in df_to.columns:
        try:
            col_vals = set(df_to[col].dropna().astype(str).unique())
            if vals & col_vals:
                return col
        except Exception:
            continue
    return None

# ---------------------------
# Cargar hojas (automático, público)
# ---------------------------
sheets = load_public_sheet_dict(GOOGLE_SHEET_URL)
if not sheets:
    st.sidebar.error("No se pudieron cargar las hojas desde la URL pública configurada. Verificá la URL y que el archivo sea público.")
    st.stop()

# Detectar la hoja principal de Espacio Curricular (varios nombres posibles)
def first_sheet_like(cands):
    for cand in cands:
        for name, df in sheets.items():
            if cand.lower() in name.lower():
                return name, df
    return None, None

name_esp, df_esp = first_sheet_like(["ESPACIO_CURRICULAR_SA","ESPACIO_CURRICULAR","ESPACIO CURRICULAR","ESPACIO_CURRICULAR_SA","ESPACIO_CURRICULAR_SA".lower()])
if df_esp is None:
    df_esp = pd.DataFrame()

# hoja contenidos
name_cont, df_cont = first_sheet_like(["CONTENIDOS_PRODUCIDOS","CONTENIDOS_PRODUCIDOS","CONTENIDOS","Contenidos_Producidos","CONTENIDOS_PRODUCIDOS"])
if df_cont is None:
    df_cont = pd.DataFrame()

# ---------------------------
# Extraer opciones para selects (modalidad, años, niveles, materias)
# ---------------------------
# Modalidad: preferir columna Modalidad_Tipo en ESPACIO_CURRICULAR_SA o columna Modalidad en otra hoja
modalidad_col = None
modalidades = []
if "Modalidad_Tipo" in df_esp.columns:
    modalidad_col = "Modalidad_Tipo"
    modalidades = sorted(df_esp[modalidad_col].dropna().astype(str).unique().tolist())
else:
    # buscar columna Modalidad en otras hojas
    for name, df in sheets.items():
        if "Modalidad_Tipo" in df.columns:
            modalidad_col = "Modalidad_Tipo"
            modalidades = sorted(df["Modalidad_Tipo"].dropna().astype(str).unique().tolist())
            break
        if "Modalidad" in df.columns:
            modalidad_col = "Modalidad"
            modalidades = sorted(df["Modalidad"].dropna().astype(str).unique().tolist())
            break

# Años / Niveles: en ESPACIO_CURRICULAR_SA la columna puede llamarse "Año/Nivel" o "Año" o "Año/Nivel"
anio_candidates = [c for c in ["Año/Nivel","Año","ANIO","Año_Nivel","Año Nivel","Año / Nivel"] if c in df_esp.columns]
anio_col = anio_candidates[0] if anio_candidates else None
anios_raw = []
if anio_col:
    anios_raw = sorted(df_esp[anio_col].dropna().astype(str).unique().tolist())

# normalizar para mostrar "1º año" ... "6º año"
def normalizar_anio_label(x):
    m = re.search(r"(\d+)", str(x))
    if m:
        return f"{int(m.group(1))}º año"
    return str(x)

anios = [normalizar_anio_label(a) for a in anios_raw]

# niveles (podemos mostrar igual que años porque pueden coincidir)
niveles = anios.copy()

# Materias: columnas candidatas en ESPACIO_CURRICULAR_SA
materia_candidate_cols = []
for c in ["MateriasAgrupadas","Nombre_Espacio_curricular","Nombre_Espacio_Curricular","Nombre de especialidad curricular","Materias","Nombre"]:
    if c in df_esp.columns:
        materia_candidate_cols.append(c)
# fallback: cualquier columna que contenga "mater" y "espac"
if not materia_candidate_cols:
    for c in df_esp.columns:
        if "mater" in c.lower() and "espac" in c.lower():
            materia_candidate_cols.append(c)
# extraer materias únicas (separando por comas)
materias = extract_unique_subjects(df_esp, materia_candidate_cols) if materia_candidate_cols else []

# ---------------------------
# Layout: sidebar con avatar (limpio) y main con filtros
# ---------------------------
st.title("🎓 Tutor IA para Profesores — Buscador de contenidos")

# Sidebar minimalista con avatar
with st.sidebar:
    st.header("Avatar del Tutor")
    avatar_mode = st.radio("Elegí avatar", options=["Preset: Femenino","Preset: Masculino","Preset: Robot","Subir imagen (.png/.jpg/.gif)"], index=0)
    avatar_bytes = None
    if avatar_mode.startswith("Preset"):
        # enlaces a imágenes públicas pequeñas (puedes usar locales si las guardás en assets/)
        presets = {
            "Preset: Femenino": "https://cdn-icons-png.flaticon.com/512/1995/1995574.png",
            "Preset: Masculino": "https://cdn-icons-png.flaticon.com/512/1996/1996372.png",
            "Preset: Robot": "https://cdn-icons-png.flaticon.com/512/4714/4714149.png"
        }
        st.image(presets.get(avatar_mode), width=140)
    else:
        up = st.file_uploader("Subí imagen o GIF", type=["png","jpg","jpeg","gif"])
        if up:
            avatar_bytes = up.read()
            st.image(avatar_bytes, width=140)

    st.markdown("---")
    st.caption("El avatar ayudará al docente con breves consejos contextuales.")

# Controles principales (fila de selects)
col1, col2, col3, col4 = st.columns([1,1,1,1])
with col1:
    opciones_modalidad = ["(no seleccionar)"] + modalidades if modalidades else ["(no seleccionar)"]
    modalidad_sel = st.selectbox("🏫 Modalidad", opciones_modalidad, index=0, key="sel_modalidad")
with col2:
    opciones_anio = ["(no seleccionar)"] + anios if anios else ["(no seleccionar)"]
    anio_sel = st.selectbox("📘 Año (visual)", opciones_anio, index=0, key="sel_anio")
with col3:
    opciones_nivel = ["(no seleccionar)"] + niveles if niveles else ["(no seleccionar)"]
    nivel_sel = st.selectbox("📗 Nivel", opciones_nivel, index=0, key="sel_nivel")
with col4:
    opciones_materia = ["(no seleccionar)"] + materias if materias else ["(no seleccionar)"]
    materia_sel = st.selectbox("📚 Materia", opciones_materia, index=0, key="sel_materia")

st.markdown("---")

# Acción: buscar
buscar = st.button("🔎 Buscar contenidos y recursos")

# ---------------------------
# Procesar búsqueda cuando se presiona
# ---------------------------
if buscar:
    # Validaciones
    if materia_sel == "(no seleccionar)":
        st.info("Elegí una materia para buscar contenidos (o deja materia vacía para ver ejemplos según filtros).")
    else:
        # crear df_search partiendo de df_esp
        df_search = df_esp.copy() if not df_esp.empty else pd.DataFrame()

        # filtrar por modalidad si la columna existe en df_esp
        if modalidad_sel != "(no seleccionar)":
            if modalidad_col and modalidad_col in df_search.columns:
                df_search = df_search[df_search[modalidad_col].astype(str).str.contains(re.escape(modalidad_sel), case=False, na=False)]
        # filtrar por año (buscamos número)
        if anio_sel != "(no seleccionar)" and anio_col:
            m = re.search(r"(\d+)", anio_sel)
            target = m.group(1) if m else anio_sel
            df_search = df_search[df_search[anio_col].astype(str).str.contains(str(target), na=False)]
        # filtrar por nivel (tratamos similar a año porque en tu dataset se solapan)
        if nivel_sel != "(no seleccionar)" and anio_col:
            m = re.search(r"(\d+)", nivel_sel)
            target = m.group(1) if m else nivel_sel
            df_search = df_search[df_search[anio_col].astype(str).str.contains(str(target), na=False)]
        # filtrar por materia: la celda puede contener varias materias separadas; hacemos match exacto entre los elementos
        if materia_sel != "(no seleccionar)" and materia_candidate_cols:
            def materia_match(cell):
                s = str(cell)
                parts = re.split(r"\s*[,;]\s*", s)
                return any(p.strip().lower() == materia_sel.strip().lower() for p in parts)
            mask = False
            for c in materia_candidate_cols:
                if c in df_search.columns:
                    try:
                        mask_col = df_search[c].astype(str).apply(materia_match)
                        mask = mask | mask_col
                    except Exception:
                        continue
            df_search = df_search[mask]

        # mostrar resumen limpio de filtros aplicados
        st.subheader("Filtros aplicados")
        st.write(f"- Modalidad: **{modalidad_sel}**")
        st.write(f"- Año (visual): **{anio_sel}**")
        st.write(f"- Nivel: **{nivel_sel}**")
        st.write(f"- Materia: **{materia_sel}**")

        if df_search.empty:
            st.warning("No se encontraron filas en 'ESPACIO_CURRICULAR' que coincidan con los filtros.")
        else:
            # Intentar relacionar con CONTENIDOS_PRODUCIDOS (df_cont)
            df_content = df_cont.copy() if not df_cont.empty else pd.DataFrame()
            matched_contents = pd.DataFrame()

            if not df_content.empty:
                # 1) intentar encontrar columna que haga join (valores comunes)
                link_col = find_link_column(df_search, df_content)
                if link_col:
                    # keys desde la primera columna de df_search (ej: codigo)
                    key_col = df_search.columns[0]
                    keys = df_search[key_col].dropna().astype(str).unique().tolist()
                    matched_contents = df_content[df_content[link_col].astype(str).isin(keys)]
                # 2) fallback por buscar materia en Titulo/Descripcion/TipoContenido_Nombre/Nombre_Espacio
                if matched_contents.empty:
                    search_cols = []
                    for c in ["Titulo","titulo","Descripcion","descripcion","TipoContenido_Nombre","TipoContenido","Nombre_Espacio_curricular","Nombre_Espacio_Curricular","MateriasAgrupadas"]:
                        if c in df_content.columns:
                            search_cols.append(c)
                    # buscar cadena materia_sel en cualquiera de esas columnas
                    regex = re.escape(materia_sel)
                    frames = []
                    for c in search_cols:
                        try:
                            frames.append(df_content[df_content[c].astype(str).str.contains(regex, case=False, na=False)])
                        except Exception:
                            continue
                    if frames:
                        matched_contents = pd.concat(frames).drop_duplicates().reset_index(drop=True)

            # Mostrar resultados (solo campos relevantes)
            st.markdown("### 📘 Contenidos encontrados")
            if matched_contents is None or matched_contents.empty:
                st.info("No se encontraron contenidos asociados en la hoja 'CONTENIDOS_PRODUCIDOS'.")
                # mostrar resumen de filas de referencia (sin columnas técnicas)
                st.markdown("**Filas de referencia (Espacio Curricular):**")
                for _, r in df_search.head(6).iterrows():
                    # mostrar solo: materia, año/nivel, modalidad si existen
                    parts = []
                    for key in [materia_candidate_cols[0] if materia_candidate_cols else None, anio_col, modalidad_col]:
                        if key and key in r.index and pd.notna(r[key]) and str(r[key]).strip() != "":
                            parts.append(f"**{key}**: {short_text(r[key], 80)}")
                    if parts:
                        st.markdown(" • " + " — ".join(parts))
            else:
                # elegimos columnas de salida en orden preferido
                for _, row in matched_contents.iterrows():
                    titulo = (row.get("Titulo") or row.get("titulo") or row.get("Title") or "").strip()
                    desc = (row.get("Descripcion") or row.get("descripcion") or row.get("Description") or "").strip()
                    tipo = (row.get("TipoContenido_Nombre") or row.get("TipoContenido") or "").strip()
                    urlc = (row.get("URL_Contenido") or row.get("URL") or row.get("Url") or row.get("Enlace") or "").strip()

                    st.markdown("---")
                    st.markdown(f"**{titulo or 'Sin título'}**")
                    if tipo:
                        st.markdown(f"*Tipo:* {tipo}")
                    if desc:
                        st.write(short_text(desc, 700))
                    if urlc:
                        # mostrar como enlace clicable
                        st.markdown(f"[Ir al recurso]({urlc})")

        # burbujita del avatar con consejo (si existe)
        st.markdown(
            """
            <div style='background:#e8f6ff;border-radius:10px;padding:12px;margin-top:12px;'>
            🗨️ <b>Consejo del Tutor:</b> Si no encontrás contenidos, probá quitar filtros o buscar por palabras clave del tema (por ejemplo: 'fracciones', 'teorema'). También podés pedir al propietario del Sheet que agregue enlaces en la columna URL_Contenido.
            </div>
            """, unsafe_allow_html=True
        )

# ---------------------------
# Footer: instrucciones mínimas
# ---------------------------
st.markdown("---")
st.info("Si querés compartir esta demo públicamente: desplegala en Streamlit Cloud, Railway o exponela con ngrok para pruebas. Si la hoja es privada, hay que compartirla públicamente o con una cuenta de servicio.")
