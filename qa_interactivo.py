# qa_interactivo.py
import pandas as pd
from transformers import pipeline

# -------------------------
# 1️⃣ Cargar Excel
# -------------------------
excel_path = "data/tu_archivo.xlsx"  # reemplazar con el nombre real
xls = pd.ExcelFile(excel_path)
print("Hojas disponibles:", xls.sheet_names)

# Elegir hoja
hoja = input("Escribí el nombre de la hoja que querés usar: ")
df = pd.read_excel(xls, sheet_name=hoja)

print(f"\nColumnas disponibles en la hoja '{hoja}':", df.columns.tolist())
print("Primeras filas de datos:\n", df.head())

# -------------------------
# 2️⃣ Preparar modelo QA
# -------------------------
qa_model = pipeline("question-answering")

# -------------------------
# 3️⃣ Función para preguntar
# -------------------------
def preguntar_ia(pregunta, dataframe):
    # Convertir Excel a texto simple
    contexto = ""
    for col in dataframe.columns:
        contexto += f"{col}: {dataframe[col].astype(str).tolist()}\n"
    
    resultado = qa_model(question=pregunta, context=contexto)
    return resultado['answer']

# -------------------------
# 4️⃣ Bucle interactivo de preguntas
# -------------------------
respuestas = []

print("\nEscribí tus preguntas (o 'salir' para terminar):")
while True:
    pregunta = input("Pregunta: ")
    if pregunta.lower() == "salir":
        break
    try:
        respuesta = preguntar_ia(pregunta, df)
        print("Respuesta:", respuesta)
        respuestas.append((pregunta, respuesta))
    except Exception as e:
        print("Error al procesar la pregunta:", e)

# -------------------------
# 5️⃣ Guardar respuestas (opcional)
# -------------------------
guardar = input("\nQuerés guardar las respuestas en un archivo CSV? (si/no): ")
if guardar.lower() == "si":
    salida_path = "respuestas_ia.csv"
    pd.DataFrame(respuestas, columns=["Pregunta", "Respuesta"]).to_csv(salida_path, index=False)
    print(f"Respuestas guardadas en '{salida_path}'")
