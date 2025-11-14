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

