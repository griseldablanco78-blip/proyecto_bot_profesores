# Proyecto: Bot simple (consola) — configurado para tu archivo

**Ubicación del Excel (según lo indicado):**

`C:\Users\grise\OneDrive\Escritorio\proyecto Gobierno de la ciudad\proyecto_bot_profesores\Ecosistema_modelo_BD -Equipo de prácticas.xlsx`

> He dejado todo el proyecto listo para ejecutar en tu PC (copia el contenido de cada archivo en la estructura indicada). Si el nombre del archivo es distinto o no tiene extensión `.xlsx`, cambialo en `src/indexer.py` y en `README.txt`.

---

## Estructura del proyecto

```
proyecto_bot_profesores/
├─ data/
│   └─ Ecosistema_modelo_BD -Equipo de prácticas.xlsx
├─ index/
│   └─ (faiss.index se generará aquí)
├─ src/
│   ├─ indexer.py
│   └─ chat.py
├─ requirements.txt
└─ README.txt
```

---

## requirements.txt

```
pandas
sentence-transformers
faiss-cpu
tqdm
openai
python-dotenv
```

---

## src/indexer.py

```python
# src/indexer.py
import os
import json
import argparse
import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from tqdm import tqdm

# Ruta por defecto a tu archivo (modifica si tu archivo tiene otro nombre)
excel_path_default = r"C:\Users\grise\OneDrive\Escritorio\proyecto Gobierno de la ciudad\proyecto_bot_profesores\Ecosistema_modelo_BD -Equipo de prácticas.xlsx"


def build_documents_from_excel(excel_path):
    sheets = pd.read_excel(excel_path, sheet_name=None)
    documents = []
    for sheet_name, df in sheets.items():
        df = df.fillna("")
        for idx, row in df.iterrows():
            parts = []
            for col in df.columns:
                val = str(row[col]).strip()
                if val:
                    parts.append(f"{col}: {val}")
            text = "\n".join(parts).strip()
            if not text:
                continue
            doc = {
                "text": text,
                "metadata": {
                    "sheet": sheet_name,
                    "row_index": int(idx)
                }
            }
            documents.append(doc)
    return documents


def index_documents(documents, model_name="all-MiniLM-L6-v2", index_path="index/faiss.index", meta_path="index/metadata.json"):
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    model = SentenceTransformer(model_name)
    texts = [d["text"] for d in documents]
    print("Calculando embeddings...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    faiss.write_index(index, index_path)
    print(f"Índice FAISS guardado en {index_path}")

    store = [{"metadata": d["metadata"], "text": d["text"]} for d in documents]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Metadatos guardados en {meta_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", default=excel_path_default, help="ruta a tu archivo .xlsx")
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--index", default="index/faiss.index")
    parser.add_argument("--meta", default="index/metadata.json")
    args = parser.parse_args()

    if not os.path.exists(args.excel):
        print("No encontré el archivo Excel en:", args.excel)
        print("Asegurate de que el archivo exista y que la ruta sea correcta.")
        exit(1)

    docs = build_documents_from_excel(args.excel)
    print(f"Documentos extraídos: {len(docs)}")
    index_documents(docs, model_name=args.model, index_path=args.index, meta_path=args.meta)
```

---

## src/chat.py

```python
# src/chat.py
import os
import json
import argparse
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import openai
from dotenv import load_dotenv

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def load_index(index_path="index/faiss.index", meta_path="index/metadata.json"):
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError("Index o metadata no encontrados. Ejecutá indexer.py primero.")
    index = faiss.read_index(index_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta

MODEL = SentenceTransformer("all-MiniLM-L6-v2")


def retrieve(query, index, meta, top_k=4, sheet_filter=None):
    q_emb = MODEL.encode([query], convert_to_numpy=True)
    D, I = index.search(q_emb, top_k*3)
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


def summarize_with_openai(question, contexts):
    if not OPENAI_KEY:
        return None
    openai.api_key = OPENAI_KEY
    system = "Eres un asistente que responde basándose SOLO en las fuentes entregadas. Si no está en las fuentes, dilo."
    context_text = "\n\n".join([f"Fuente (sheet={c['metadata']['sheet']}, row={c['metadata']['row_index']}):\n{c['text']}" for c in contexts])
    prompt = f"Contexto:\n{context_text}\n\nPregunta: {question}\n\nResponde brevemente y cita la sheet si corresponde."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
        max_tokens=400,
        temperature=0.2
    )
    return response.choices[0].message.content.strip()


def interactive_chat(index, meta):
    print("Chat iniciado. Escribí 'exit' para salir.")
    print("Para filtrar por sheet, escribe: sheet:NOMBRE_DE_LA_SHEET tu pregunta")
    while True:
        q = input("\nPregunta> ").strip()
        if not q:
            continue
        if q.lower() in ["exit","salir","quit"]:
            print("Hasta luego.")
            break
        sheet_filter = None
        if q.lower().startswith("sheet:"):
            try:
                parts = q.split(" ", 1)
                sheet_filter = parts[0].split(":",1)[1]
                q = parts[1] if len(parts) > 1 else ""
            except:
                print("Formato de filtro inválido. Usa: sheet:NOMBRE pregunta...")
                continue
        contexts = retrieve(q, index, meta, top_k=4, sheet_filter=sheet_filter)
        if not contexts:
            print("No encontré resultados relevantes.")
            continue
        if OPENAI_KEY:
            answer = summarize_with_openai(q, contexts)
            print("\n== RESPUESTA (generada) ==\n")
            print(answer)
            print("\n== FUENTES relevantes ==\n")
            for i,c in enumerate(contexts,1):
                print(f"[{i}] sheet={c['metadata']['sheet']} row={c['metadata']['row_index']}")
                print(c['text'][:400].replace("\n", " "))
                print("----")
        else:
            print("\n== FUENTES relevantes ==\n")
            for i,c in enumerate(contexts,1):
                print(f"[{i}] sheet={c['metadata']['sheet']} row={c['metadata']['row_index']}")
                print(c['text'][:800])
                print("----")
            print("\n(Si querés respuestas redactadas automáticamente, exporta tu OPENAI_API_KEY en un archivo .env)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="index/faiss.index")
    parser.add_argument("--meta", default="index/metadata.json")
    args = parser.parse_args()
    idx, meta = load_index(args.index, args.meta)
    interactive_chat(idx, meta)
```

---

## README.txt (instrucciones rápidas)

```
1) Coloca tu archivo Excel (Ecosistema_modelo_BD -Equipo de prácticas.xlsx) dentro de la carpeta "data".
2) Crea y activa un entorno virtual:
   python -m venv venv
   .\venv\Scripts\Activate.ps1   (PowerShell)
3) Instala dependencias:
   pip install --upgrade pip
   pip install -r requirements.txt
4) Indexa el Excel:
   python src\indexer.py --excel "C:\Users\grise\OneDrive\Escritorio\proyecto Gobierno de la ciudad\Ecosistema_modelo_BD -Equipo de prácticas.xlsx"
5) Ejecuta el chat:
   python src\chat.py

- Para filtrar por sheet usa: sheet:NOMBRE_DE_LA_SHEET tu pregunta
- Si querés respuestas redactadas automáticamente, crea un archivo .env en la raíz con:
   OPENAI_API_KEY=tu_api_key

Si tenés problemas con la ruta por los espacios, el script ya usa una r"raw string" y debería funcionar en Windows.
```

---

## Nota final

Si el archivo en tu PC tiene otro nombre exacto o extensión, editá la ruta en `src/indexer.py` (variable `excel_path_default`) o ejecutá `python src/indexer.py --excel "ruta/a/tu/archivo.xlsx"`.

Decime si querés que arme también la versión **web (Streamlit)** a continuación, o la versión con **voz**. También puedo generar un archivo ZIP con todo listo si preferís.
