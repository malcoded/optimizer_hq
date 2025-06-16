import json
import os

def load_layout(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'sPlanos' not in data or not data['sPlanos']:
        raise ValueError("Formato inválido: falta 'sPlanos'")

    if 'layout' not in data['sPlanos'][0] or not data['sPlanos'][0]['layout']:
        raise ValueError("Formato inválido: falta 'layout' en el primer plano")

    return data