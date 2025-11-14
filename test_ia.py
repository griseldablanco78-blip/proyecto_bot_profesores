# test_ia.py
import tensorflow as tf
from tensorflow import keras
from transformers import pipeline

# -------------------------
# 1️⃣ Verificar versiones
# -------------------------
print("TensorFlow version:", tf.__version__)
print("Keras version:", keras.__version__)

# -------------------------
# 2️⃣ Crear un modelo Keras de prueba
# -------------------------
model = keras.Sequential([
    keras.layers.Dense(10, activation='relu', input_shape=(5,)),
    keras.layers.Dense(1, activation='sigmoid')
])

print("\nModelo Keras de prueba:")
model.summary()

# -------------------------
# 3️⃣ Probar Transformers (Hugging Face)
# -------------------------
print("\nProbando Transformers...")
classifier = pipeline("sentiment-analysis")
result = classifier("¡Me encanta usar esta IA!")
print("Resultado de clasificación de sentimiento:", result)

# -------------------------
# 4️⃣ Hacer una predicción de ejemplo con Keras
# -------------------------
import numpy as np
sample_input = np.random.rand(1, 5)
prediction = model.predict(sample_input)
print("\nPredicción de ejemplo con Keras:", prediction)
