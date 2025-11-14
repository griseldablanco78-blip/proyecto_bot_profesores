# qa_excel.py
import pandas as pd
from transformers import pipeline

# -------------------------
# 1️⃣ Cargar el Excel
# -------------------------
excel_path = "data/tu_archivo.xlsx"  # reemplazar con el nombre real
df = pd.read_excel(excel_path)

print("Columnas disponibles en el Excel:", df.columns.tolist())
print("Primeras filas de datos:\n", df.head())

# -------------------------
# 2️⃣ Preparar modelo de pregunta-respuesta
# -------------------------
qa_model = pipeline("question-answering")

# -------------------------
# 3️⃣ Función para preguntar
# -------------------------
def preguntar_ia(pregunta, dataframe):
    # Convertir Excel a texto simple para el modelo
    contexto = ""
    for col in dataframe.columns:
        contexto += f"{col}: {dataframe[col].astype(str).tolist()}\n"
    
    resultado = qa_model(question=pregunta, context=contexto)
    return resultado

# -------------------------
# 4️⃣ Ejemplo de preguntas
# -------------------------
pregunta1 = "¿Cuál es el valor de la primera fila en la columna Nombre?"  # ejemplo
respuesta = preguntar_ia(pregunta1, df)
print("\nPregunta:", pregunta1)
print("Respuesta:", respuesta['answer'])
