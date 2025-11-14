# src/chat_incremental.py
import os
import json
import argparse
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from dotenv import load_dotenv
import datetime
import csv

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Paths
INDEX_PATH = "index/faiss.index"
META_PATH = "index/metadata.json"
LOG_PATH = "index/query_log.csv"

MODEL_NAME = "all-MiniLM-L6-v2"

# Cargar modelo (una vez)
MODEL = SentenceTransformer(MODEL_NAME)

def ensure_index_files():
    if not os.path.exists("index"):
        os.makedirs("index", exist_ok=True)
    if not os.path.exists(META_PATH):
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

def load_index_and_meta():
    ensure_index_files()
    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
    else:
        # índice vacío (dim se definirá al primer add)
        index = None
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta

def save_index(index):
    faiss.write_index(index, INDEX_PATH)

def save_meta(meta):
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def add_document_to_index(text, metadata, index, meta):
    emb = MODEL.encode([text], convert_to_numpy=True)
    if index is None:
        dim = emb.shape[1]
        index = faiss.IndexFlatL2(dim)
    index.add(emb)
    meta.append({"metadata": metadata, "text": text})
    save_index(index)
    save_meta(meta)
    return index, meta

def retrieve(query, index, meta, top_k=4, sheet_filter=None):
    if index is None:
        return []
    q_emb = MODEL.encode([query], convert_to_numpy=True)
    D, I = index.search(q_emb, min(top_k*3, max(1, index.ntotal)))
    results = []
    for idx in I[0]:
        if idx < 0:
            continue
        item = meta[idx]
        if sheet_filter:
            if item["metadata"].get("sheet", "").lower() != sheet_filter.lower():
                continue
        results.append(item)
        if len(results) >= top_k:
            break
    return results

def log_query(question, response, contexts):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    headers = ["timestamp","question","response","contexts"]
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(headers)
        ctx_short = " | ".join([f"{c['metadata'].get('sheet')}#{c['metadata'].get('row_index')}" for c in contexts])
        writer.writerow([datetime.datetime.now().isoformat(), question, response.replace("\n"," "), ctx_short])

def ask_openai(question, contexts):
    if not OPENAI_KEY:
        return None
    import openai
    openai.api_key = OPENAI_KEY
    system = "Eres un asistente pedagógico que sugiere mejoras y alternativas didácticas basadas en las fuentes entregadas."
    context_text = "\n\n".join([f"Fuente (sheet={c['metadata']['sheet']}, row={c['metadata']['row_index']}):\n{c['text']}" for c in contexts])
    prompt = f"Contexto:\n{context_text}\n\nPregunta: {question}\n\nProponé 3 alternativas prácticas y breves para que un profesor mejore la propuesta, indicando recursos y actividades."
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        max_tokens=400,
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()

def interactive_loop():
    print("Bot (incremental) iniciado. Comandos especiales:")
    print(" - Para filtrar por sheet: sheet:Nombre pregunta")
    print(" - Para añadir un consejo/entrada y que se indexe ahora: add:SheetName|TextoTitulo|TextoCuerpo")
    print(" - Para pedir sugerencias/alternativas de mejora (usa OpenAI si tenés key): suggest:Materia|Año|Pregunta")
    print(" - Ver log: log")
    print(" - Salir: exit\n")

    index, meta = load_index_and_meta()
    while True:
        q = input("Pregunta> ").strip()
        if not q:
            continue
        if q.lower() in ["exit","salir","quit"]:
            print("Chau.")
            break
        if q.lower() == "log":
            if os.path.exists(LOG_PATH):
                with open(LOG_PATH,"r",encoding="utf-8") as f:
                    print(f.read())
            else:
                print("No hay log todavía.")
            continue

        # Comando ADD: add:Sheet|Titulo|Cuerpo
        if q.lower().startswith("add:"):
            try:
                payload = q.split(":",1)[1]
                sheet,name,body = payload.split("|",2)
                text = f"Titulo: {name}\nContenido: {body}"
                metadata = {"sheet": sheet, "row_index": f"manual_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"}
                index, meta = add_document_to_index(text, metadata, index, meta)
                print("Entrada añadida e indexada ✅")
            except Exception as e:
                print("Error en formato add. Usa: add:SheetName|Titulo|Cuerpo")
            continue

        # Comando SUGGEST: suggest:Materia|Año|Consulta
        if q.lower().startswith("suggest:"):
            try:
                payload = q.split(":",1)[1]
                materia,anio,consulta = payload.split("|",2)
                # buscamos en sheet por materia o año
                sheet_filter = None
                # intentar filtrar por materia
                sheet_filter = materia
                index, meta = load_index_and_meta()
                contexts = retrieve(consulta, index, meta, top_k=6, sheet_filter=sheet_filter)
                suggestion = ask_openai(consulta, contexts)
                if suggestion:
                    print("\n== Sugerencias del modelo ==\n")
                    print(suggestion)
                    log_query(q, suggestion, contexts)
                else:
                    print("No hay OpenAI API key. Mostrando fuentes relevantes:\n")
                    for i,c in enumerate(contexts,1):
                        print(f"[{i}] sheet={c['metadata']['sheet']} row={c['metadata']['row_index']}")
                        print(c['text'][:400])
                        print("----")
                continue
            except Exception as e:
                print("Error en formato suggest. Usa: suggest:Materia|Año|Consulta")
                continue

        # filtro por sheet: sheet:NAME question
        sheet_filter = None
        if q.lower().startswith("sheet:"):
            try:
                parts = q.split(" ",1)
                sheet_filter = parts[0].split(":",1)[1]
                q = parts[1] if len(parts)>1 else ""
            except:
                print("Formato sheet inválido. Usa: sheet:NOMBRE pregunta...")
                continue

        index, meta = load_index_and_meta()
        contexts = retrieve(q, index, meta, top_k=5, sheet_filter=sheet_filter)
        if not contexts:
            print("No encontré resultados relevantes.")
            log_query(q, "No results", [])
            continue

        # Si hay OpenAI, pedimos redacción/sugerencias, si no, mostramos contexto
        if OPENAI_KEY:
            answer = ask_openai(q, contexts)
            if not answer:
                answer = "No pude generar respuesta con OpenAI."
            print("\n== RESPUESTA GENERADA ==\n")
            print(answer)
            print("\n== FUENTES ==\n")
            for i,c in enumerate(contexts,1):
                print(f"[{i}] sheet={c['metadata']['sheet']} row={c['metadata']['row_index']}")
                print(c['text'][:400].replace("\n"," "))
                print("----")
            log_query(q, answer, contexts)
        else:
            print("\n== FUENTES RELEVANTES ==\n")
            for i,c in enumerate(contexts,1):
                print(f"[{i}] sheet={c['metadata']['sheet']} row={c['metadata']['row_index']}")
                print(c['text'][:800])
                print("----")
            print("\n(Para respuestas redactadas automáticamente, poné OPENAI_API_KEY en .env)")
            log_query(q, "Shown sources only", contexts)

if __name__ == "__main__":
    interactive_loop()
