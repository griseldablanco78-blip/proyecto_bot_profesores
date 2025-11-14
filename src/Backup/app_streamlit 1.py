import streamlit as st
import pandas as pd
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Tutor IA para Profesores", page_icon="🎓", layout="wide")

st.title("🎓 Tutor IA para Profesores")
st.write("Bienvenido/a. Este asistente puede ayudarte a consultar información del ecosistema educativo y darte consejos personalizados.")

# Ruta al archivo Excel
excel_path = os.path.join("data", "Base de Datos Ecosistema Secundaria Aprende.xlsx")

# --- CARGA DEL EXCEL ---
if os.path.exists(excel_path):
    try:
        xls = pd.ExcelFile(excel_path)
        st.sidebar.success("📘 Archivo Excel cargado correctamente.")
        st.sidebar.write(f"Hojas detectadas: {', '.join(xls.sheet_names)}")
    except Exception as e:
        st.sidebar.error(f"Error al leer el Excel: {e}")
else:
    st.sidebar.warning("⚠️ No se encontró el archivo Excel en la carpeta 'data'.")

# --- CHAT SIMULADO ---
# --- Reemplazar la sección de chat por este bloque (modo guiado + respuestas) ---
import re
from pathlib import Path

st.header("Chat del Tutor — Modo guiado")
st.markdown("Si no sabés qué preguntar, activá **Modo guiado** y elegí una plantilla rápida. También podés escribir tu propia pregunta.")

# asumimos que df_dict fue cargado antes (ver pasos previos)
# si no existe, intentamos cargar automáticamente (código tolerante)
if 'df_dict' not in locals():
    data_folder = Path(os.getcwd()) / "data"
    files = list(data_folder.glob("*.xlsx"))
    df_dict = {}
    if files:
        try:
            df_dict = pd.read_excel(files[0], sheet_name=None)
        except Exception as e:
            st.error("No pude leer el Excel: " + str(e))

# construir listas dinámicas
sheet_names = sorted(list(df_dict.keys())) if df_dict else []
# intentar extraer valores de 'Materia' y 'Año' buscando columnas comunes
possible_subjects = set()
possible_years = set()
for sheet, df in (df_dict.items() if df_dict else []):
    cols = [c.lower() for c in df.columns]
    # buscar columna con 'mater' o 'asign' o 'disciplina'
    subj_col = None
    for c in df.columns:
        if re.search(r"materi|asign|discipl", c, re.I):
            subj_col = c; break
    # buscar columna con 'año' o 'año' variants or 'year' or 'curso'
    year_col = None
    for c in df.columns:
        if re.search(r"año|anio|year|curso|grado", c, re.I):
            year_col = c; break
    if subj_col:
        possible_subjects.update(df[subj_col].dropna().astype(str).unique().tolist())
    if year_col:
        possible_years.update(df[year_col].dropna().astype(str).unique().tolist())

possible_subjects = sorted([s for s in possible_subjects if s and len(s) < 60])[:200]
possible_years = sorted([y for y in possible_years if y and len(y) < 20])[:200]

with st.expander("Modo guiado (sugerencias de preguntas)"):
    guided = st.checkbox("Activar modo guiado", value=True)
    # sugerencias automáticas basadas en hojas
    if guided:
        st.write("Sugerencias rápidas (hacé clic para cargar en la caja de pregunta):")
        # plantillas generales
        general_templates = [
            "¿Qué contenidos recomienda la materia {subject} para el {year} año?",
            "Proponé 3 actividades prácticas para trabajar {topic} en {subject} ({year} año).",
            "¿Qué evaluación sugerida hay para {subject} en {year} año?",
            "¿Qué competencias se trabajan en {subject} relacionadas con {topic}?",
            "¿Qué recursos digitales se sugieren para enseñar {topic} en {subject}?"
        ]
        # mostrar selects para subject/year/topic
        subj_choice = None
        year_choice = None
        if possible_subjects:
            subj_choice = st.selectbox("Seleccioná materia (para plantillas)", options=["(no usar)"] + possible_subjects)
        else:
            subj_choice = st.text_input("Materia (opcional)")
        if possible_years:
            year_choice = st.selectbox("Seleccioná año/curso (para plantillas)", options=["(no usar)"] + possible_years)
        else:
            year_choice = st.text_input("Año/Curso (opcional)")

        # topic libre
        topic_input = st.text_input("Tema / tópico (ej: fracciones, comprensión lectora)")

        # generar botones para cada template
        cols = st.columns(2)
        for i, templ in enumerate(general_templates):
            with cols[i % 2]:
                filled = templ.format(
                    subject=(subj_choice if subj_choice and subj_choice != "(no usar)" else "{subject}"),
                    year=(year_choice if year_choice and year_choice != "(no usar)" else "{year}"),
                    topic=(topic_input if topic_input else "{topic}")
                )
                if st.button(filled[:60]+"...", key=f"g{i}"):
                    # rellenar la caja de pregunta
                    st.session_state['guided_question'] = filled

# input principal (se usa session_state para que los botones carguen texto)
if 'guided_question' not in st.session_state:
    st.session_state['guided_question'] = ""

user_input = st.text_input("Tu pregunta (puede venir del modo guiado):", value=st.session_state['guided_question'], key="user_q")
col_left, col_right = st.columns([3,1])
with col_right:
    if st.button("Consultar"):
        q = user_input.strip()
        if not q:
            st.info("Escribí o elegí una pregunta.")
        else:
            # lógica de búsqueda: usar índice si existe
            index_exists = os.path.exists(os.path.join("index","faiss.index")) and os.path.exists(os.path.join("index","metadata.json"))
            if index_exists:
                # usamos retrieve() si tu app ya tiene la función definidia; si no, definimos simple retrieval aquí
                try:
                    # si retrieve ya existe en el archivo lo llamamos
                    contexts = retrieve(q, top_k=6, sheet_filter=None)
                except Exception:
                    # fallback: uso local simple (buscar substring en textos)
                    with open(os.path.join("index","metadata.json"),"r",encoding="utf-8") as f:
                        meta = json.load(f)
                    hits = []
                    qlow = q.lower().split()
                    for i,item in enumerate(meta):
                        txt = item.get("text","").lower()
                        # conteo simple de coincidencias
                        score = sum(1 for w in qlow if w and w in txt)
                        if score>0:
                            hits.append((score, i, item))
                    hits = sorted(hits, key=lambda x: -x[0])[:6]
                    contexts = [h[2] for h in hits]
            else:
                # no hay índice: buscar en df_dict
                hits = []
                qwords = [w.lower() for w in re.findall(r'\w+', q)]
                for sheet, df in (df_dict.items() if df_dict else []):
                    # concatenar fila a texto
                    for idx, row in df.fillna("").iterrows():
                        text = " ".join([str(v) for v in row.values])
                        score = sum(1 for w in qwords if w in text.lower())
                        if score>0:
                            hits.append((score, sheet, idx, text))
                hits = sorted(hits, key=lambda x: -x[0])[:10]
                contexts = []
                for sc, sheet, idx, text in hits:
                    contexts.append({"metadata":{"sheet":sheet,"row_index":idx},"text":text})

            # mostrar resultados
            if not contexts:
                st.warning("No encontré resultados relevantes.")
            else:
                st.subheader("Fuentes / hallazgos relevantes")
                for i,c in enumerate(contexts,1):
                    st.markdown(f"**[{i}] sheet={c['metadata'].get('sheet')} row={c['metadata'].get('row_index')}**")
                    st.write(c['text'][:800])
                    st.markdown("---")

                # si tenés OpenAI, generar redacción / sugerencias
                if OPENAI_KEY:
                    try:
                        import openai
                        openai.api_key = OPENAI_KEY
                        system = "Eres un asistente pedagógico que sugiere actividades y mejoras breves."
                        context_text = "\n\n".join([f"Fuente (sheet={c['metadata']['sheet']}, row={c['metadata']['row_index']}):\n{c['text']}" for c in contexts])
                        prompt = f"Contexto:\n{context_text}\n\nPregunta: {q}\n\nProponé 3 alternativas prácticas y breves para un docente."
                        with st.spinner("Generando respuesta con LLM..."):
                            resp = openai.ChatCompletion.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
                                max_tokens=450,
                                temperature=0.3
                            )
                            answer = resp.choices[0].message.content.strip()
                        st.subheader("Respuesta sugerida (LLM)")
                        st.write(answer)
                    except Exception as e:
                        st.error("No se pudo generar respuesta LLM: " + str(e))
                else:
                    st.info("Si querés respuestas redondeadas automáticamente, poné OPENAI_API_KEY en .env")
