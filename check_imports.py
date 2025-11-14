import sys

modules = [
    "tensorflow",
    "keras",
    "pandas",
    "numpy",
    "matplotlib",
    "sklearn"
]

for module in modules:
    try:
        __import__(module)
        print(f"✅ {module} importado correctamente.")
    except ImportError:
        print(f"❌ {module} no está instalado.")

        