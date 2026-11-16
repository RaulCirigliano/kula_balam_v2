#!/usr/bin/env python3
"""
Prueba Aislada de Estrategia 01 — Test de Carga y Evaluación Autónoma de Qwen 2.5
Ejecuta la inferencia directamente contra Ollama sin intermediarios deterministas.
"""

import json
import time
import requests
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESTRATEGIA_PATH = os.path.join(PROJECT_ROOT, "estrategia_01.json")

def main():
    print("=" * 70)
    print("🔬 [FASE 2] PRUEBA AISLADA DE ESTRATEGIA 01 — CEREBRO QWEN 2.5")
    print("=" * 70)

    # 1. Cargar archivo de estrategia
    with open(ESTRATEGIA_PATH, "r", encoding="utf-8") as f:
        estrategia = json.load(f)

    modelo = estrategia.get("modelo", "qwen2.5-coder:7b")
    prompt_template = estrategia.get("prompt_base", "")

    print(f"📦 Estrategia cargada: {estrategia.get('id_estrategia')}")
    print(f"🧠 Modelo objetivo: {modelo}")
    print("-" * 70)

    # Casos de prueba
    casos = [
        {
            "nombre": "Caso 1: Datos reales del Log de Raúl (Mercado en Corrección)",
            "datos_mercado": {
                "activo": "SOL/USDT",
                "precio_cierre": 102.85,
                "ema200": 104.50,
                "sma20": 103.41,
                "rsi": 38.5,
                "rvol": 0.76,
                "posicion_abierta": False
            },
            "esperado": "ESPERAR"
        },
        {
            "nombre": "Caso 2: Setup Alcista Perfecto (Supera EMA200, SMA20, RSI > 40, RVOL > 0.8)",
            "datos_mercado": {
                "activo": "BTC/USDT",
                "precio_cierre": 82500.0,
                "ema200": 81500.0,
                "sma20": 82000.0,
                "rsi": 58.2,
                "rvol": 1.45,
                "posicion_abierta": False
            },
            "esperado": "COMPRAR"
        },
        {
            "nombre": "Caso 3: Señal de Salida (Posición Comprada con Precio bajo SMA20)",
            "datos_mercado": {
                "activo": "BTC/USDT",
                "precio_cierre": 80900.0,
                "ema200": 80000.0,
                "sma20": 81500.0,
                "rsi": 42.0,
                "rvol": 0.95,
                "posicion_abierta": True,
                "precio_entrada": 82500.0
            },
            "esperado": "VENDER"
        }
    ]

    for idx, caso in enumerate(casos, 1):
        print(f"\n▶ Ejecutando {caso['nombre']}...")
        prompt_final = prompt_template.replace("{datos_mercado}", json.dumps(caso["datos_mercado"], indent=2))

        payload = {
            "model": modelo,
            "prompt": prompt_final,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9
            }
        }

        t_inicio = time.time()
        try:
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
            latencia = round(time.time() - t_inicio, 2)
            
            if res.status_code != 200:
                print(f"❌ Error HTTP {res.status_code} desde Ollama: {res.text}")
                continue

            raw_text = res.json().get("response", "").strip()
            print(f"⏱️ Tiempo de respuesta: {latencia}s")
            print(f"📄 Respuesta cruda de Qwen:")
            print(raw_text)

            # Validar formato JSON estricto
            parsed = json.loads(raw_text)
            accion = parsed.get("accion")
            confianza = parsed.get("confianza")
            motivo = parsed.get("motivo")

            status = "✅ APROBADO" if accion == caso["esperado"] else "⚠️ DISCREPANCIA"
            print(f"{status} -> Acción: '{accion}' (Esperado: '{caso['esperado']}') | Confianza: {confianza}%")
            print(f"Motivo técnico: {motivo}")

        except requests.exceptions.Timeout:
            print(f"❌ TIMEOUT: Ollama tardó más de 30s en responder.")
        except json.JSONDecodeError as jde:
            print(f"❌ ERROR JSON: La respuesta no es un JSON válido: {jde}")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")

    print("\n" + "=" * 70)
    print("🏁 Fin de la prueba aislada.")
    print("=" * 70)

if __name__ == "__main__":
    main()
