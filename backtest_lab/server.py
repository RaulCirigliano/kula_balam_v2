import sys
import os
import re
import json
import uuid
import subprocess
import tempfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("backtest_lab.server")

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Kula Balam - Backtest Lab")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "datos_historicos"
HISTORIAL_DIR = BASE_DIR / "historial"
ESTRATEGIAS_DIR = BASE_DIR / "estrategias"
HIST_META = HISTORIAL_DIR / "metadata.json"
META_FILE = ESTRATEGIAS_DIR / "metadata.json"
ESTRATEGIAS_IA_DIR = BASE_DIR / "estrategias_ia"
ESTRATEGIAS_MATH_DIR = BASE_DIR / "estrategias_math"
ESTRATEGIAS_HEREDADAS_DIR = BASE_DIR / "estrategias_heredadas"
PROMOVIDAS_DIR = BASE_DIR / "promovidas"
META_IA = ESTRATEGIAS_IA_DIR / "metadata.json"
META_MATH = ESTRATEGIAS_MATH_DIR / "metadata.json"
META_HEREDADAS = ESTRATEGIAS_HEREDADAS_DIR / "metadata.json"

# Asegurar directorios
DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORIAL_DIR.mkdir(parents=True, exist_ok=True)
ESTRATEGIAS_DIR.mkdir(parents=True, exist_ok=True)
ESTRATEGIAS_IA_DIR.mkdir(parents=True, exist_ok=True)
ESTRATEGIAS_MATH_DIR.mkdir(parents=True, exist_ok=True)
ESTRATEGIAS_HEREDADAS_DIR.mkdir(parents=True, exist_ok=True)
PROMOVIDAS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# 1. DATASETS
# ---------------------------------------------------------
@app.get("/api/datasets")
def list_datasets():
    archivos = sorted([f.name for f in DATA_DIR.glob("*.parquet")] + [f.name for f in DATA_DIR.glob("*.csv")])
    return {"datos_historicos": archivos}

# ---------------------------------------------------------
# 2. HISTORIAL DE AUDITORÍAS (POSITIVAS ARRIBA)
# ---------------------------------------------------------
@app.get("/api/historial")
def list_historial():
    meta = {}
    if HIST_META.exists():
        try:
            meta = json.loads(HIST_META.read_text(encoding="utf-8"))
        except Exception:
            pass
    archivos = sorted([f.name for f in HISTORIAL_DIR.glob("*.py")])
    return [{"nombre": f, "comentario": meta.get(f, "")} for f in archivos]

@app.get("/api/historial/{nombre}")
def get_historial(nombre: str):
    p = HISTORIAL_DIR / nombre
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"nombre": nombre, "codigo": p.read_text(encoding="utf-8")}

# ---------------------------------------------------------
# 3. MIS FÓRMULAS GUARDADAS (PERSONAL)
# ---------------------------------------------------------
def _leer_meta_pers():
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

@app.get("/api/estrategias")
def list_guardadas():
    meta = _leer_meta_pers()
    archivos = sorted([f.name for f in ESTRATEGIAS_DIR.glob("*.py")])
    return [{"nombre": f, "comentario": meta.get(f, "")} for f in archivos]

@app.get("/api/estrategias/{nombre}")
def get_guardada(nombre: str):
    p = ESTRATEGIAS_DIR / nombre
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"nombre": nombre, "codigo": p.read_text(encoding="utf-8")}

class GuardarReq(BaseModel):
    nombre: str
    codigo: str
    comentario: str = ""

@app.post("/api/estrategias/guardar")
def guardar_formula(req: GuardarReq):
    nom = req.nombre.strip()
    if not nom.endswith(".py"):
        nom += ".py"
    nom = Path(nom).name
    
    # 1. Guardar en Mis Fórmulas
    (ESTRATEGIAS_DIR / nom).write_text(req.codigo, encoding="utf-8")
    meta = _leer_meta_pers()
    meta[nom] = req.comentario.strip()
    META_FILE.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Guardar también en Historial para tener acceso unificado
    (HISTORIAL_DIR / nom).write_text(req.codigo, encoding="utf-8")
    hist_meta = {}
    if HIST_META.exists():
        try:
            hist_meta = json.loads(HIST_META.read_text(encoding="utf-8"))
        except Exception:
            pass
    hist_meta[nom] = req.comentario.strip()
    HIST_META.write_text(json.dumps(hist_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"status": "ok", "archivo": nom, "comentario": meta[nom]}

# ---------------------------------------------------------
# 4. MÓDULO ESTRATEGIAS DE IA (CEREBRO ANTIGRAVITY CIO)
# ---------------------------------------------------------
def _ordenar_por_metadata(directorio: Path, meta: dict) -> list:
    en_disco = {f.name for f in directorio.glob("*.py")}
    ordenados = [k for k in meta.keys() if k in en_disco]
    restantes = sorted(en_disco - set(ordenados))
    return ordenados + restantes

@app.get("/api/estrategias_ia")
def list_ia():
    meta = json.loads(META_IA.read_text(encoding="utf-8")) if META_IA.exists() else {}
    files = _ordenar_por_metadata(ESTRATEGIAS_IA_DIR, meta)
    return [{"nombre": f, "comentario": meta.get(f, "")} for f in files]

@app.get("/api/estrategias_ia/{nombre}")
def get_ia(nombre: str):
    p = ESTRATEGIAS_IA_DIR / nombre
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Estrategia IA no encontrada")
    return {"nombre": nombre, "codigo": p.read_text(encoding="utf-8")}

@app.post("/api/estrategias_ia/guardar")
def guardar_ia(req: GuardarReq):
    nom = req.nombre.strip()
    if not nom.endswith(".py"):
        nom += ".py"
    nom = Path(nom).name
    (ESTRATEGIAS_IA_DIR / nom).write_text(req.codigo, encoding="utf-8")
    meta = json.loads(META_IA.read_text(encoding="utf-8")) if META_IA.exists() else {}
    meta[nom] = req.comentario.strip()
    META_IA.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "archivo": nom, "comentario": meta[nom]}

# ---------------------------------------------------------
# 5. MÓDULO FÓRMULAS MATEMÁTICAS PURAS
# ---------------------------------------------------------
@app.get("/api/estrategias_math")
def list_math():
    meta = json.loads(META_MATH.read_text(encoding="utf-8")) if META_MATH.exists() else {}
    files = _ordenar_por_metadata(ESTRATEGIAS_MATH_DIR, meta)
    return [{"nombre": f, "comentario": meta.get(f, "")} for f in files]

@app.get("/api/estrategias_math/{nombre}")
def get_math(nombre: str):
    p = ESTRATEGIAS_MATH_DIR / nombre
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Fórmula matemática no encontrada")
    cod = p.read_text(encoding="utf-8")
    import re
    m_arb = re.search(r'^\s*ARBITRO_IA\s*=\s*["\']([^"\']+)["\']', cod, re.MULTILINE)
    arb_sug = m_arb.group(1).strip() if m_arb else ""
    return {"nombre": nombre, "codigo": cod, "arbitro_sugerido": arb_sug}

@app.post("/api/estrategias_math/guardar")
def guardar_math(req: GuardarReq):
    nom = req.nombre.strip()
    if not nom.endswith(".py"):
        nom += ".py"
    nom = Path(nom).name
    (ESTRATEGIAS_MATH_DIR / nom).write_text(req.codigo, encoding="utf-8")
    meta = json.loads(META_MATH.read_text(encoding="utf-8")) if META_MATH.exists() else {}
    meta[nom] = req.comentario.strip()
    META_MATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "archivo": nom, "comentario": meta[nom]}

# ---------------------------------------------------------
# 5.0 CATÁLOGO DINÁMICO DE FÓRMULAS DEL SISTEMA (SSOT)
# ---------------------------------------------------------
@app.get("/api/catalogo_formulas")
def api_get_catalogo_formulas():
    try:
        from backend.estrategias.catalogo_manager import get_catalogo_completo
    except ImportError:
        import sys
        sys.path.insert(0, str(BASE_DIR.parent))
        from backend.estrategias.catalogo_manager import get_catalogo_completo
    return get_catalogo_completo()


@app.get("/api/catalogo_formulas/{categoria}/{archivo}")
def api_get_formula_detalle(categoria: str, archivo: str):
    try:
        from backend.estrategias.catalogo_manager import get_formula_detalle
    except ImportError:
        import sys
        sys.path.insert(0, str(BASE_DIR.parent))
        from backend.estrategias.catalogo_manager import get_formula_detalle
    res = get_formula_detalle(categoria, archivo)
    if not res:
        raise HTTPException(status_code=404, detail=f"Fórmula '{archivo}' no encontrada en categoría '{categoria}'")
    return res


@app.delete("/api/catalogo_formulas/{categoria}/{archivo}")
def api_delete_formula(categoria: str, archivo: str):
    try:
        from backend.estrategias.catalogo_manager import eliminar_formula
    except ImportError:
        import sys
        sys.path.insert(0, str(BASE_DIR.parent))
        from backend.estrategias.catalogo_manager import eliminar_formula
    try:
        return eliminar_formula(categoria, archivo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando fórmula: {str(e)}")

# ---------------------------------------------------------
# 5.0.1 ENDPOINTS UNIFICADOS PARA LAS 3 ESTACIONES DEL LAB
# ---------------------------------------------------------
@app.get("/api/lab/estrategias_unificadas")
def api_get_estrategias_unificadas():
    """
    Retorna la lista organizada para el selector unificado de la Estación 1:
    - Grupo produccion: Panel Principal y Operador Presente (SSOT)
    - Grupo laboratorio: Ganadoras/Heredadas en pruebas y fórmulas del taller local
    """
    try:
        from backend.estrategias.catalogo_manager import get_catalogo_completo
    except ImportError:
        import sys
        sys.path.insert(0, str(BASE_DIR.parent))
        from backend.estrategias.catalogo_manager import get_catalogo_completo

    import re

    def _limpiar_doble_icono(t: str) -> str:
        s = str(t or "").strip()
        # SALVAGUARDA C (Anti-Doble Prefijo): Remueve emojis sueltos al inicio si van seguidos inmediatamente por el doble icono
        s = re.sub(r'^[🚀🏺🏆🛡️⚡🌊🐅🕯️📐🏛️🐘🧲🏃🐻🔱🎯]\s+([🌊⚡🐅🕯️📐🏛️🐘🧲🏃🐻🔱🎯🏆🤖])', r'\1', s)
        return s

    cat = get_catalogo_completo()
    produccion = []
    for item in cat.get("panel_principal", []):
        produccion.append({
            **item,
            "titulo": _limpiar_doble_icono(item.get("titulo", "")),
            "categoria": "principal",
            "origen": "🏛️ Panel Principal"
        })
    for item in cat.get("operador_presente", []):
        produccion.append({
            **item,
            "titulo": _limpiar_doble_icono(item.get("titulo", "")),
            "categoria": "operador_presente",
            "origen": "⚡ Con Operador"
        })

    laboratorio = []
    archivos_vistos = set()
    for item in cat.get("para_testear", {}).get("ganadoras", []):
        archivos_vistos.add(item["archivo"])
        laboratorio.append({
            **item,
            "titulo": _limpiar_doble_icono(item.get("titulo", "")),
            "categoria": "para_testear_ganadoras",
            "origen": "🚀 Ganadora Lab"
        })
    for item in cat.get("para_testear", {}).get("heredadas", []):
        archivos_vistos.add(item["archivo"])
        laboratorio.append({
            **item,
            "titulo": _limpiar_doble_icono(item.get("titulo", "")),
            "categoria": "para_testear_heredadas",
            "origen": "🏺 Heredada"
        })

    # Incorporar fórmulas locales de estrategias_math no incluidas aún
    LISTA_NEGRA_ESTRATEGIAS = {
        "tendencia_optimizada_auto.py",
        "tendencia_optimizada_experimental.py",
        "4_tendencia_optimizada_auto.py",
        "donchian_breakout_eth_usdt_4h.py",
    }
    meta_m = json.loads(META_MATH.read_text(encoding="utf-8")) if META_MATH.exists() else {}
    for f in sorted(ESTRATEGIAS_MATH_DIR.glob("*.py")):
        if f.name in LISTA_NEGRA_ESTRATEGIAS or f.name.startswith("tendencia_optimizada_"):
            continue
        if f.name not in archivos_vistos:
            archivos_vistos.add(f.name)
            info = meta_m.get(f.name, "")
            comentario = info if isinstance(info, str) else info.get("comentario", f.stem)
            laboratorio.append({
                "archivo": f.name,
                "categoria": "math",
                "id": f.stem,
                "titulo": _limpiar_doble_icono(comentario or f.stem),
                "subtitulo": "Taller Local Math",
                "timeframe": "4h",
                "dataset_sugerido": "AUTO",
                "origen": "🧪 Taller Lab"
            })

    return {
        "status": "ok",
        "produccion": produccion,
        "laboratorio": laboratorio
    }


class GuardarCarpetaLabRequest(BaseModel):
    nombre: str
    comentario: Optional[str] = "Estrategia guardada en Lab"
    code_math: str
    code_ia: Optional[str] = ""
    ticker: Optional[str] = "binance_SOL_USDT_4h.parquet"


@app.post("/api/lab/guardar_en_carpeta_lab")
def api_guardar_en_carpeta_lab(req: GuardarCarpetaLabRequest):
    """
    Guarda la estrategia unificada en la Carpeta Lab (backend/estrategias/catalogo/para_testear/ganadoras/)
    y sincroniza copia local en backtest_lab/estrategias_math/ sin tocar el TraderDaemon.
    """
    nombre = str(req.nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre de archivo requerido")
    if not nombre.endswith(".py"):
        nombre += ".py"

    comentario = str(req.comentario or "").strip() or "Estrategia guardada en Lab"
    code_math = str(req.code_math or "").strip()
    code_ia = str(req.code_ia or "").strip()
    ticker = str(req.ticker or "binance_SOL_USDT_4h.parquet").strip()

    if not code_math:
        raise HTTPException(status_code=400, detail="El código matemático no puede estar vacío")

    # Archivo unificado
    codigo_unificado = code_math
    if code_ia:
        codigo_unificado += "\n\n# --- ÁRBITRO HEURÍSTICO IA ---\n" + code_ia

    # 1. Guardar en catálogo para_testear/ganadoras/
    try:
        from backend.estrategias.catalogo_manager import GANADORAS_DIR, _read_metadata, _write_metadata
        if GANADORAS_DIR.exists():
            dest = GANADORAS_DIR / nombre
            dest.write_text(codigo_unificado, encoding="utf-8")
            meta = _read_metadata(GANADORAS_DIR)
            meta[nombre] = {
                "id": Path(nombre).stem,
                "titulo": comentario,
                "descripcion": comentario,
                "dataset_sugerido": ticker if ticker != "AUTO" else "binance_SOL_USDT_4h.parquet",
                "timeframe": "1d" if "1d" in ticker.lower() else ("15m" if "15m" in ticker.lower() else "4h"),
                "rendimiento_lab": "Guardada en Lab"
            }
            _write_metadata(GANADORAS_DIR, meta)
    except Exception as e:
        logger.warning(f"No se pudo guardar en catalogo/ganadoras: {e}")

    # 2. Sincronizar en backtest_lab/estrategias_math/
    p_math = ESTRATEGIAS_MATH_DIR / nombre
    p_math.write_text(code_math, encoding="utf-8")
    meta_m = json.loads(META_MATH.read_text(encoding="utf-8")) if META_MATH.exists() else {}
    meta_m[nombre] = {"comentario": comentario, "arbitro_sugerido": f"arbitro_{nombre}" if code_ia else None}
    META_MATH.write_text(json.dumps(meta_m, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Si hay código IA, guardar en backtest_lab/estrategias_ia/
    if code_ia:
        nom_ia = f"arbitro_{nombre}"
        p_ia = ESTRATEGIAS_IA_DIR / nom_ia
        p_ia.write_text(code_ia, encoding="utf-8")
        meta_ia = json.loads(META_IA.read_text(encoding="utf-8")) if META_IA.exists() else {}
        meta_ia[nom_ia] = {"comentario": f"Árbitro de {nombre}"}
        META_IA.write_text(json.dumps(meta_ia, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "ok",
        "archivo": nombre,
        "categoria": "para_testear_ganadoras",
        "mensaje": f"Estrategia '{nombre}' guardada exitosamente en Carpeta Lab."
    }

# ---------------------------------------------------------
# 5.1 ESTRATEGIAS HEREDADAS (CONTENEDOR DE AUDITORÍA Y RECUPERACIÓN)
# ---------------------------------------------------------
@app.get("/api/estrategias_heredadas")
def list_estrategias_heredadas():
    meta = json.loads(META_HEREDADAS.read_text(encoding="utf-8")) if META_HEREDADAS.exists() else {}
    files = sorted([f.name for f in ESTRATEGIAS_HEREDADAS_DIR.glob("*.py")])
    result = []
    for f in files:
        info = meta.get(f, {})
        result.append({
            "archivo": f,
            "titulo": info.get("titulo", f),
            "descripcion": info.get("descripcion", ""),
            "dataset_sugerido": info.get("dataset_sugerido", "binance_BTC_USDT_4h.parquet")
        })
    return result

@app.get("/api/estrategias_heredadas/{nombre}")
def get_estrategia_heredada(nombre: str):
    p = ESTRATEGIAS_HEREDADAS_DIR / nombre
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Estrategia heredada no encontrada")
    cod = p.read_text(encoding="utf-8")
    meta = json.loads(META_HEREDADAS.read_text(encoding="utf-8")) if META_HEREDADAS.exists() else {}
    info = meta.get(nombre, {})
    
    code_math = cod
    code_ia = ""
    if "def arbitro_ia(" in cod:
        parts = cod.split("def arbitro_ia(")
        code_math = parts[0].strip()
        code_ia = "# -*- coding: utf-8 -*-\n'''\nÁrbitro IA Heredado\n'''\ndef arbitro_ia(" + parts[1]
    
    return {
        "archivo": nombre,
        "titulo": info.get("titulo", nombre),
        "descripcion": info.get("descripcion", ""),
        "dataset_sugerido": info.get("dataset_sugerido", "binance_BTC_USDT_4h.parquet"),
        "code_math": code_math,
        "code_ia": code_ia
    }

# ---------------------------------------------------------
# 5.2 PLANTILLAS INSTITUCIONALES (CARGA DIRECTA DE CÓDIGO)
# ---------------------------------------------------------
PLANTILLAS_INSTITUCIONALES_DEF = {
    "donchian_sol": {
        "titulo": "🛡️ Donchian Squeeze 4H (SOL · Lote Dinámico)",
        "prompt": "Ruptura de Canal Donchian de 30 periodos en SOL/USDT 4H con compresión de volatilidad (Squeeze), filtro tendencial EMA 200 alcista, Stop Loss a 1.6 ATR y Take Profit a 4.16 ATR (R:R 1:2.6). Árbitro de volumen que vete secado (RVOL < 1.20) y mechas trampa.",
        "dataset": "binance_SOL_USDT_4h.parquet"
    },
    "donchian_btc": {
        "titulo": "🛡️ Donchian Squeeze 4H (BTC · Lote Dinámico)",
        "prompt": "Ruptura institucional de Canal Donchian en BTC/USDT 4H con filtro de pendiente positiva en EMA 200, SL en 1.6 ATR y TP en 4.16 ATR (R:R 1:2.60). Árbitro IA que exija absorción con RVOL >= 1.20.",
        "dataset": "binance_BTC_USDT_4h.parquet"
    },
    "vwap_eth": {
        "titulo": "🎯 Reversión VWAP ±1.5σ (ETH 15M · Lote 0.01)",
        "prompt": "Estrategia de reversión a la media estadística en bandas de VWAP ±1.5 desviaciones en ETH/USDT 15M con mecha de absorción mínima del 18%, SL 1.2 ATR y TP 2.6 ATR (R:R 1:2.16).",
        "dataset": "binance_ETH_USDT_15m.parquet"
    },
    "fibo_btc": {
        "titulo": "🌊 Pullback Fibo EMA50 (BTC 4H · Lote 0.01)",
        "prompt": "Pullback a zona dorada Fibonacci (0.50 a 0.618) y rebote en EMA 50 en BTC/USDT 4H con tendencia macro EMA 50 > EMA 200, SL 1.3 ATR y TP 2.86 ATR (R:R 1:2.20).",
        "dataset": "binance_BTC_USDT_4h.parquet"
    },
    "momentum_qqq": {
        "titulo": "📈 Ruptura Momentum 1D (QQQ · Acciones)",
        "prompt": "Ruptura de Momentum diario en QQQ (1D) tras contracción de volatilidad, con filtro de tendencia EMA 200 y filtro de régimen institucional.",
        "dataset": "yf_QQQ_1d.parquet"
    }
}

@app.get("/api/plantillas_institucionales/{tipo}")
def get_plantilla_institucional(tipo: str):
    if tipo not in PLANTILLAS_INSTITUCIONALES_DEF:
        raise HTTPException(status_code=404, detail="Plantilla institucional no encontrada")
    info = PLANTILLAS_INSTITUCIONALES_DEF[tipo]
    try:
        from backtest_lab.generador_ia import sintetizar_estrategia
    except ImportError:
        from generador_ia import sintetizar_estrategia
    res = sintetizar_estrategia(info["prompt"], motor="auto", ticker_hint=info["dataset"])
    return {
        "tipo": tipo,
        "titulo": info["titulo"],
        "prompt": info["prompt"],
        "nombre": res.get("nombre", f"{tipo}.py"),
        "comentario": res.get("comentario", info["titulo"]),
        "dataset_recomendado": res.get("dataset_recomendado", info["dataset"]),
        "code_math": res.get("code_math", ""),
        "code_ia": res.get("code_ia", "")
    }

# ---------------------------------------------------------
# 6. ENSAMBLADOR Y EJECUTOR DE CÓDIGO (SANDBOX DUAL)
# ---------------------------------------------------------
def generar_script_ejecucion(
    code_math: str,
    code_ia: str,
    code_testigo: str = "",
    modo_escalado: bool = False,
    slot_capital: float = 25.0,
    riesgo_base: float = 0.50,
    riesgo_escalado: float = 1.00,
    umbral_escalado: float = 35.0,
    umbral_desescalado: float = 30.0,
    nombre_estrategia: str = "",
) -> str:
    tiene_ia = bool(code_ia and any(w in code_ia for w in ["def arbitro_ia", "arbitro_ia(", "def custom_brain_filter", "custom_brain_filter("]))
    tiene_ia_math = bool(code_math and any(w in code_math for w in ["def arbitro_ia", "arbitro_ia(", "def custom_brain_filter", "custom_brain_filter("]))
    tiene_testigo_input = bool(code_testigo and any(k in code_testigo for k in ["VELA_TESTIGO", "close", "rvol", "close_offset_pct"]))
    tiene_testigo_math = bool("VELA_TESTIGO" in code_math)
    
    script = f'''# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from typing import Dict, Tuple

BASE_LAB_DIR = Path({repr(str(BASE_DIR))})
if str(BASE_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_LAB_DIR))

import numpy as np
import pandas as pd
from core.metrics import EvaluadorCuantitativo

NOMBRE_ESTRATEGIA = {repr(nombre_estrategia or "Fórmula Matemática")}
MODO_ESCALADO = {repr(modo_escalado)}
SLOT_CAPITAL = float({slot_capital})
RIESGO_BASE = float({riesgo_base})
RIESGO_ESCALADO = float({riesgo_escalado})
UMBRAL_ESCALADO = float({umbral_escalado})
UMBRAL_DESESCALADO = float({umbral_desescalado})

# ==========================================
# CÓDIGO MATEMÁTICO PURO
# ==========================================
{code_math}

# ==========================================
# CÓDIGO DEL ÁRBITRO DE IA Y CEREBRO KULA
# ==========================================
TIENE_IA = True
'''
    if tiene_ia:
        script += f'''
TIENE_IA_CODIGO = True
{code_ia}
'''
    elif tiene_ia_math:
        script += '''
TIENE_IA_CODIGO = True
'''
    else:
        arb_cargado = ""
        import re
        m_arb = re.search(r'ARBITRO_IA\s*=\s*[\'"]([^\'"]+)[\'"]', code_math)
        if m_arb:
            p_arb = ESTRATEGIAS_IA_DIR / m_arb.group(1).strip()
            if p_arb.exists():
                try:
                    arb_cargado = p_arb.read_text(encoding="utf-8")
                except Exception:
                    arb_cargado = ""
        if arb_cargado:
            script += f'''
TIENE_IA_CODIGO = True
{arb_cargado}
'''
        else:
            script += '''
TIENE_IA_CODIGO = False
def arbitro_ia(fila, lado, entry, sl, tp):
    return True, 1.0, "OK_BASE_KULA"
'''

    if tiene_testigo_input:
        script += f'''
# ==========================================
# PARÁMETROS VELA TESTIGO (GROUND TRUTH)
# ==========================================
TIENE_TESTIGO = True
{code_testigo}
if "VELA_TESTIGO" not in globals() and isinstance(locals().get("VELA_TESTIGO"), dict):
    VELA_TESTIGO = locals()["VELA_TESTIGO"]
'''
    elif tiene_testigo_math:
        script += '''
# ==========================================
# PARÁMETROS VELA TESTIGO (GROUND TRUTH DESDE FÓRMULA)
# ==========================================
TIENE_TESTIGO = True
if "VELA_TESTIGO" not in globals() and isinstance(locals().get("VELA_TESTIGO"), dict):
    VELA_TESTIGO = locals()["VELA_TESTIGO"]
'''
    else:
        script += '''
# ==========================================
# PARÁMETROS VELA TESTIGO (GROUND TRUTH)
# ==========================================
TIENE_TESTIGO = False
VELA_TESTIGO = None
'''

    script += '''
# ==========================================
# REGLAS Y CANDADOS DE KULA BALAM
# ==========================================
def check_universal_wick_veto_local(df_slice: pd.DataFrame, side: str, max_wick_ratio: float = 0.50):
    if len(df_slice) < 1:
        return None
    last_c = df_slice.iloc[-1]
    high = float(last_c.get("high", 0.0))
    low = float(last_c.get("low", 0.0))
    open_p = float(last_c.get("open", 0.0))
    close_p = float(last_c.get("close", 0.0))
    total_rng = high - low
    if total_rng <= 1e-8:
        return None
    if str(side).upper() == "LONG":
        upper_wick = high - max(open_p, close_p)
        if upper_wick / total_rng >= max_wick_ratio:
            return f"VETO UNIVERSAL MECHA: Mecha superior {upper_wick/total_rng:.1%} >= {max_wick_ratio:.0%}"
    elif str(side).upper() == "SHORT":
        lower_wick = min(open_p, close_p) - low
        if lower_wick / total_rng >= max_wick_ratio:
            return f"VETO UNIVERSAL MECHA: Mecha inferior {lower_wick/total_rng:.1%} >= {max_wick_ratio:.0%}"
    return None

# ==========================================
# MOTOR DEL LABORATORIO (DATOS Y EJECUCIÓN)
# ==========================================
def preparar_mercado(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if not isinstance(df.index, pd.DatetimeIndex):
        col_t = next((c for c in ["datetime", "timestamp", "date", "time"] if c in df.columns), None)
        if col_t:
            s_t = df[col_t]
            if pd.api.types.is_numeric_dtype(s_t):
                unit = "ms" if float(s_t.iloc[0]) > 1e11 else "s"
                df[col_t] = pd.to_datetime(s_t, unit=unit, utc=True)
            else:
                df[col_t] = pd.to_datetime(s_t, utc=True)
            df.set_index(col_t, inplace=True)
        else:
            raise ValueError("No se detectó columna temporal válida.")
    df = df.sort_index()
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = df[c].astype(float)

    prev_c = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean().shift(1)

    vol_col = "volume" if "volume" in df.columns else None
    if vol_col and df[vol_col].sum() > 0:
        df["vol_sma"] = df[vol_col].rolling(20).mean().shift(1)
        df["rvol"] = df[vol_col] / (df["vol_sma"] + 1e-9)
    else:
        df["rvol"] = 1.3
    df["rvol_3_prev"] = df["rvol"].shift(1).rolling(3, min_periods=1).mean().fillna(1.0)

    rango = (df["high"] - df["low"]).replace(0, 1e-9)
    techo = df[["open", "close"]].max(axis=1)
    suelo = df[["open", "close"]].min(axis=1)
    df["mecha_superior_pct"] = ((df["high"] - techo) / rango) * 100.0
    df["mecha_inferior_pct"] = ((suelo - df["low"]) / rango) * 100.0
    df["cuerpo_pct"] = ((df["close"] - df["open"]).abs() / rango) * 100.0
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["dist_ema_atrs"] = (df["close"] - df["ema_50"]).abs() / (df["atr"] + 1e-9)
    df["dist_ema200_atrs"] = (df["close"] - df["ema_200"]) / (df["atr"] + 1e-9)
    df["ema_200_slope"] = (df["ema_200"] - df["ema_200"].shift(5)) / (df["atr"] + 1e-9)
    cambio_neto_20 = (df["close"] - df["close"].shift(20)).abs()
    volatilidad_ruta_20 = df["close"].diff().abs().rolling(20).sum()
    df["er_20"] = (cambio_neto_20 / (volatilidad_ruta_20 + 1e-9)).fillna(0.3)
    return df

def simular(df: pd.DataFrame, ticker: str):
    ticker_upper = ticker.upper()
    if any(fx in ticker_upper for fx in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD"]):
        comision, slippage = 0.0001, 0.00005  # ~3 pips en Forex (Manual Black 1.2)
        tipo_mercado = "Forex Spot (~3 pips / 0.03% Round-Trip)"
    elif any(st in ticker_upper for st in ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "AVGO", "GOOGL", "AMZN", "META", "TSLA"]):
        comision, slippage = 0.0002, 0.0003  # ~0.10% en Acciones/ETFs
        tipo_mercado = "TradFi Acciones/ETFs (0.10% Round-Trip)"
    else:
        comision, slippage = 0.0008, 0.0005  # 0.26% en Cripto
        tipo_mercado = "Cripto Institucional (0.26% Round-Trip)"

    evaluador = EvaluadorCuantitativo(comision_pct=comision, slippage_pct=slippage)
    trades_math = []
    trades_ia = []
    vetos_ia = []

    nombre_display = NOMBRE_ESTRATEGIA if NOMBRE_ESTRATEGIA else "Fórmula Matemática"
    print("=" * 90)
    print(f"   🏛️  FÓRMULA / ESTRATEGIA EVALUADA : {nombre_display.upper()}")
    print("=" * 90)

    if TIENE_TESTIGO and VELA_TESTIGO and isinstance(VELA_TESTIGO, dict):
        print("\\n" + "=" * 90)
        print("   BLOQUE 1: AUDITORÍA DE VELA TESTIGO (GROUND TRUTH CONTROLADO)")
        print("=" * 90)
        try:
            df_test = df.copy()
            cols_c = [c for c in df_test.columns if str(c).startswith("_")]
            if cols_c:
                df_test = df_test.drop(columns=cols_c)

            usado_historico = False
            if "fecha_historica" in VELA_TESTIGO and isinstance(df_test.index, pd.DatetimeIndex):
                try:
                    ts_obj = pd.Timestamp(VELA_TESTIGO["fecha_historica"])
                    if ts_obj.tzinfo is None and df_test.index.tz is not None:
                        ts_obj = ts_obj.tz_localize("UTC")
                    pos_arr = df_test.index.get_indexer([ts_obj], method="nearest")
                    if len(pos_arr) > 0 and pos_arr[0] >= 50:
                        idx_h = int(pos_arr[0])
                        if abs((df_test.index[idx_h] - ts_obj).total_seconds()) <= 14400:
                            es_c_h, l_h, sl_h, tp_h = formula_matematica(df_test, idx_h)
                            if es_c_h:
                                usado_historico = True
                                f_h = df_test.iloc[idx_h]
                                print(f"[*] Vela Testigo Real ({str(df_test.index[idx_h])[:16]} UTC): Open={float(f_h['open']):.2f} | High={float(f_h['high']):.2f} | Low={float(f_h['low']):.2f} | Close={float(f_h['close']):.2f} | RVOL={float(f_h.get('rvol', 1.0)):.2f}x")
                                print(f"[+] ¿Fórmula Matemática la captó? : ✅ SÍ (Señal: {l_h} | SL: {sl_h:.2f} | TP: {tp_h:.2f})")
                                if TIENE_IA:
                                    t_ok, t_sz, t_motivo = arbitro_ia(f_h, l_h, float(f_h["close"]), sl_h, tp_h)
                                    if t_ok:
                                        print(f"[+] ¿Árbitro IA la autorizó?      : ✅ SÍ (Multiplicador: {t_sz:.2f}x | {t_motivo})")
                                        print(">> DICTAMEN DE AUDITORÍA: Código de estrategia y árbitro 100% OPERATIVOS.")
                                    else:
                                        print(f"[-] ¿Árbitro IA la autorizó?      : ❌ VETADA ({t_motivo})")
                                        print(">> DICTAMEN DE AUDITORÍA: La fórmula matemática respondió, pero el Árbitro IA bloqueó la señal.")
                                else:
                                    print(">> DICTAMEN DE AUDITORÍA: La fórmula matemática está 100% OPERATIVA (Sin filtro de IA).")
                except Exception:
                    usado_historico = False

            if not usado_historico:
                idx_ultimo = len(df_test) - 1
                fila_base = df_test.iloc[idx_ultimo].to_dict()
                close_base = float(fila_base.get("close", 100.0))

                # 1. Acondicionamiento de vela previa (Paso 1 de la secuencia si se especifica)
                idx_prev = idx_ultimo - 1
                vol_mean = float(df_test["volume"].tail(20).mean()) if "volume" in df_test.columns else 1000.0
                if "vela_previa" in VELA_TESTIGO and isinstance(VELA_TESTIGO["vela_previa"], dict):
                    cfg_prev = VELA_TESTIGO["vela_previa"]
                    c_prev_ref = float(df_test.iloc[idx_prev - 1]["close"]) if idx_prev > 0 else close_base
                    drop_pct = float(cfg_prev.get("drop_pct", -1.5)) / 100.0
                    p_prev_close = c_prev_ref * (1.0 + drop_pct)
                    df_test.loc[df_test.index[idx_prev], "open"] = c_prev_ref
                    df_test.loc[df_test.index[idx_prev], "close"] = p_prev_close
                    df_test.loc[df_test.index[idx_prev], "high"] = max(c_prev_ref, p_prev_close) * 1.001
                    df_test.loc[df_test.index[idx_prev], "low"] = min(c_prev_ref, p_prev_close) * 0.998
                    if "volume" in df_test.columns:
                        df_test.loc[df_test.index[idx_prev], "volume"] = vol_mean * float(cfg_prev.get("rvol", 1.5))

                precio_incompatible = False
                if "close" in VELA_TESTIGO:
                    p_c = float(VELA_TESTIGO["close"])
                    if (abs(p_c - close_base) / close_base) < 0.35:
                        t_close = p_c
                    else:
                        precio_incompatible = True
                        t_close = close_base * (1.0 + float(VELA_TESTIGO.get("close_offset_pct", 0.015)))
                elif VELA_TESTIGO.get("recupera_ema", False):
                    ema_50_approx = float(df_test["close"].ewm(span=50, adjust=False).mean().iloc[idx_ultimo])
                    t_close = max(ema_50_approx * 1.003, (p_prev_close if "vela_previa" in VELA_TESTIGO else close_base) * 1.015)
                elif "close_offset_pct" in VELA_TESTIGO:
                    ref_p = float(df_test.loc[df_test.index[idx_prev], "close"]) if "vela_previa" in VELA_TESTIGO else close_base
                    t_close = ref_p * (1.0 + float(VELA_TESTIGO["close_offset_pct"]) / 100.0)
                else:
                    t_close = close_base * 1.015

                if precio_incompatible:
                    print(f"[!] AVISO ESCALA: Los precios de la Vela Testigo (${float(VELA_TESTIGO['close']):.2f}) son de otro activo (la serie actual cotiza en ${close_base:.2f}). Se aplicó escala porcentual automática.")

                rvol_mult = float(VELA_TESTIGO.get("rvol", 2.0))
                m_sup = float(VELA_TESTIGO.get("mecha_sup_pct", 5.0))
                m_inf = float(VELA_TESTIGO.get("mecha_inf_pct", 5.0))
                cuerpo_req = float(VELA_TESTIGO.get("cuerpo_pct", 65.0)) / 100.0

                t_vol = float(VELA_TESTIGO.get("volume", vol_mean * rvol_mult))

                if "vela_previa" in VELA_TESTIGO and isinstance(VELA_TESTIGO["vela_previa"], dict):
                    t_open = float(df_test.loc[df_test.index[idx_prev], "close"])
                elif "open" in VELA_TESTIGO and not precio_incompatible:
                    t_open = float(VELA_TESTIGO["open"])
                else:
                    t_open = close_base

                atr_val = float(df_test["atr"].iloc[idx_ultimo]) if "atr" in df_test.columns else (t_close * 0.01)
                cuerpo_val = abs(t_close - t_open)
                rango_vela = max(cuerpo_val / max(cuerpo_req, 0.4), 1e-4)

                if "high" in VELA_TESTIGO and not precio_incompatible:
                    t_high = float(VELA_TESTIGO["high"])
                else:
                    techo = max(t_open, t_close)
                    t_high = techo + (rango_vela * (m_sup / 100.0))

                if "low" in VELA_TESTIGO and not precio_incompatible:
                    t_low = float(VELA_TESTIGO["low"])
                else:
                    suelo = min(t_open, t_close)
                    t_low = suelo - (rango_vela * (m_inf / 100.0))

                fila_base["open"] = t_open
                fila_base["high"] = t_high
                fila_base["low"] = t_low
                fila_base["close"] = t_close
                fila_base["volume"] = t_vol
                if "rvol" in df_test.columns:
                    fila_base["rvol"] = rvol_mult
                if "mecha_superior_pct" in df_test.columns:
                    fila_base["mecha_superior_pct"] = m_sup
                if "mecha_inferior_pct" in df_test.columns:
                    fila_base["mecha_inferior_pct"] = m_inf
                if "dist_ema_atrs" in df_test.columns:
                    ema_col = "ema_50" if "ema_50" in df_test.columns else "_ema_50"
                    if ema_col in df_test.columns:
                        e_v = float(df_test[ema_col].iloc[idx_ultimo])
                        fila_base["dist_ema_atrs"] = abs(t_close - e_v) / (atr_val + 1e-9)
                    else:
                        fila_base["dist_ema_atrs"] = 0.5

                df_test.loc[df_test.index[idx_ultimo]] = fila_base

                es_cand, t_lado, t_sl, t_tp = formula_matematica(df_test, idx_ultimo)
                print(f"[*] Inyección Vela Testigo: Open={t_open:.2f} | High={t_high:.2f} | Low={t_low:.2f} | Close={t_close:.2f} | RVOL={rvol_mult:.2f}x")
                if es_cand:
                    print(f"[+] ¿Fórmula Matemática la captó? : ✅ SÍ (Señal: {t_lado} | SL: {t_sl:.2f} | TP: {t_tp:.2f})")
                    if TIENE_IA:
                        t_ok, t_sz, t_motivo = arbitro_ia(df_test.iloc[idx_ultimo], t_lado, t_close, t_sl, t_tp)
                        if t_ok:
                            print(f"[+] ¿Árbitro IA la autorizó?      : ✅ SÍ (Multiplicador: {t_sz:.2f}x | {t_motivo})")
                            print(f">> DICTAMEN DE AUDITORÍA: Código de estrategia y árbitro 100% OPERATIVOS.")
                        else:
                            print(f"[-] ¿Árbitro IA la autorizó?      : ❌ VETADA ({t_motivo})")
                            print(f">> DICTAMEN DE AUDITORÍA: La fórmula matemática respondió, pero el Árbitro IA bloqueó la señal.")
                    else:
                        print(f">> DICTAMEN DE AUDITORÍA: La fórmula matemática está 100% OPERATIVA (Sin filtro de IA).")
                else:
                    print(f"[-] ¿Fórmula Matemática la captó? : ❌ NO (formula_matematica devolvió False)")
                    print(f">> DICTAMEN DE AUDITORÍA: Hay un bloqueo o discrepancia matemática en la fórmula.")
        except Exception as e_testigo:
            print(f"[!] Error al evaluar Vela Testigo: {e_testigo}")
        print("=" * 90 + "\\n")
        print("=" * 90)
        print("   BLOQUE 2: RESULTADOS EN VELAS GENERALES (MERCADO REAL HISTÓRICO)")
        print("=" * 90)

    pos_m = False
    exit_m = -1
    pos_i = False
    exit_i = -1
    total = len(df)
    indices = df.index
    corte_is = int(total * 0.70)
    max_hold = int(globals().get("MAX_BARS_HOLD", 48))
    trail_mult = float(globals().get("TRAILING_ATR_MULT", 0.0))
    be_rr = float(globals().get("BREAKEVEN_RR", 0.0))
    atr_series = df["atr"].fillna(df["close"] * 0.01).values

    for i in range(50, total - 1):
        if pos_m and i >= exit_m:
            pos_m = False
        if pos_i and i >= exit_i:
            pos_i = False

        es_candidato, lado, sl, tp = formula_matematica(df, i)
        if not es_candidato:
            continue

        raw_entry = float(df.iloc[i + 1]["open"]) if i + 1 < total else float(df.iloc[i]["close"])
        atr_slippage_k = float(globals().get("ATR_SLIPPAGE_K", 0.0))
        atr_val_i = float(atr_series[i]) if i < len(atr_series) else 0.0
        atr_ratio = (atr_val_i / raw_entry) if (raw_entry > 0 and atr_val_i > 0) else 0.0
        dynamic_slip_pct = atr_slippage_k * atr_ratio
        entry = raw_entry * (1.0 + dynamic_slip_pct) if lado == "LONG" else raw_entry * (1.0 - dynamic_slip_pct)
        riesgo_ini = max(abs(entry - float(sl)), entry * 1e-5)
        cur_sl = float(sl)
        sl_movido = False
        max_fav = entry
        p_exit = float(df["close"].iloc[min(i + max_hold, total - 1)])
        exit_bar = min(i + max_hold, total - 1)
        exit_reason = "TIME"

        for j in range(i + 1, min(i + max_hold + 1, total)):
            oj = float(df["open"].iloc[j])
            hj = float(df["high"].iloc[j])
            lj = float(df["low"].iloc[j])
            if lado == "LONG":
                hit_sl = lj <= cur_sl
                hit_tp = hj >= tp
                if hit_sl and hit_tp:
                    p_exit = min(oj, cur_sl)
                    exit_bar = j
                    exit_reason = "SL_AMBIGUOUS_GUARD"
                    break
                if hit_sl:
                    p_exit = min(oj, cur_sl)
                    exit_bar = j
                    exit_reason = "TRAIL" if sl_movido else "SL"
                    break
                if hit_tp:
                    p_exit = max(oj, float(tp))
                    exit_bar = j
                    exit_reason = "TP"
                    break
                # Actualización causal al cierre de la vela j para aplicar en j+1 (cero sesgo intrabarra)
                if hj > max_fav:
                    max_fav = hj
                if be_rr > 0.0 and (max_fav - entry) >= (be_rr * riesgo_ini):
                    be_lvl = entry * 1.003
                    if be_lvl > cur_sl:
                        cur_sl = be_lvl
                        sl_movido = True
                if trail_mult > 0.0 and (max_fav - entry) >= (1.0 * riesgo_ini):
                    tr_lvl = max_fav - (trail_mult * float(atr_series[j]))
                    if tr_lvl > cur_sl:
                        cur_sl = tr_lvl
                        sl_movido = True
            else:
                hit_sl = hj >= cur_sl
                hit_tp = lj <= tp
                if hit_sl and hit_tp:
                    p_exit = max(oj, cur_sl)
                    exit_bar = j
                    exit_reason = "SL_AMBIGUOUS_GUARD"
                    break
                if hit_sl:
                    p_exit = max(oj, cur_sl)
                    exit_bar = j
                    exit_reason = "TRAIL" if sl_movido else "SL"
                    break
                if hit_tp:
                    p_exit = min(oj, float(tp))
                    exit_bar = j
                    exit_reason = "TP"
                    break
                if lj < max_fav:
                    max_fav = lj
                if be_rr > 0.0 and (entry - max_fav) >= (be_rr * riesgo_ini):
                    be_lvl = entry * 0.997
                    if be_lvl < cur_sl:
                        cur_sl = be_lvl
                        sl_movido = True
                if trail_mult > 0.0 and (entry - max_fav) >= (1.0 * riesgo_ini):
                    tr_lvl = max_fav + (trail_mult * float(atr_series[j]))
                    if tr_lvl < cur_sl:
                        cur_sl = tr_lvl
                        sl_movido = True

        pnl_bruto = ((p_exit - entry) / entry) * 100.0 if lado == "LONG" else ((entry - p_exit) / entry) * 100.0
        es_oos = bool(i >= corte_is)
        sl_dist_pct = float((riesgo_ini / entry) * 100.0)

        if not pos_m:
            trades_math.append({"fecha": str(indices[i])[:16], "pnl_pct": pnl_bruto, "reason": exit_reason, "oos": es_oos, "sl_dist_pct": sl_dist_pct, "sizing": 1.0})
            pos_m = True
            exit_m = exit_bar

        # ==========================================
        # EVALUACIÓN DE CANDADOS DE PRODUCCIÓN KULA BALAM + GANCHO
        # ==========================================
        kula_ok = True
        motivo_kula = "OK"
        sizing_kula = 1.0

        # 1. Veto Universal de Mechas (>= 50%)
        wick_veto = check_universal_wick_veto_local(df.iloc[:i+1], lado, 0.50)
        if wick_veto:
            kula_ok = False
            motivo_kula = wick_veto

        # 2. Tope SL en TradFi 1D (max 4.8% en acciones/ETFs 1D)
        cur_sl_kula = float(sl)
        es_1d_act = ("_1D" in ticker_upper or "1D" in ticker_upper)
        es_tradfi_1d = es_1d_act and ("YF_" in ticker_upper or any(st in ticker_upper for st in ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "AVGO", "GOOGL", "AMZN", "META", "TSLA"]))
        if kula_ok and es_tradfi_1d:
            sl_dist_max = entry * 0.048
            if abs(entry - cur_sl_kula) > sl_dist_max:
                cur_sl_kula = entry - sl_dist_max if lado == "LONG" else entry + sl_dist_max

        # 3. Escudo anti-cuchillo en LONG
        if kula_ok and lado == "LONG":
            if i >= 2 and (df["close"].iloc[i] < df["open"].iloc[i] and df["close"].iloc[i-1] < df["open"].iloc[i-1] and df["close"].iloc[i-2] < df["open"].iloc[i-2]):
                kula_ok = False
                motivo_kula = "VETO CEREBRO KULA: Escudo Anti-Cuchillo (3 velas bajistas consecutivas)"
            elif (df["open"].iloc[i] - df["close"].iloc[i]) > (1.2 * atr_series[i]):
                kula_ok = False
                motivo_kula = "VETO CEREBRO KULA: Escudo Anti-Cuchillo (Caída violenta > 1.2 ATR)"

        # 4. Asimetría neta mínima (R:R >= 1.80 tras comisiones)
        if kula_ok:
            sl_d = abs(entry - cur_sl_kula) / entry * 100.0
            tp_d = abs(float(tp) - entry) / entry * 100.0
            friccion_pct = evaluador.friccion_roundtrip * 100.0
            net_rr_calc = (tp_d - friccion_pct) / (sl_d + friccion_pct + 1e-9)
            if net_rr_calc < 1.80:
                kula_ok = False
                motivo_kula = f"VETO CEREBRO KULA: Asimetría neta insuficiente ({net_rr_calc:.2f} < 1.80)"

        # 5. Gancho custom_brain_filter o arbitro_ia
        if kula_ok:
            if "custom_brain_filter" in globals() and callable(globals()["custom_brain_filter"]):
                try:
                    cbf = globals()["custom_brain_filter"](df, i, lado, entry, cur_sl_kula, float(tp))
                    if isinstance(cbf, tuple):
                        c_ok = cbf[0]
                        c_mot = cbf[1] if len(cbf) == 2 else cbf[2]
                        c_sz = cbf[1] if len(cbf) >= 3 and isinstance(cbf[1], (int, float)) else 1.0
                    else:
                        c_ok = bool(cbf)
                        c_mot = "CUSTOM_BRAIN"
                        c_sz = 1.0
                    if not c_ok:
                        kula_ok = False
                        motivo_kula = f"VETO CUSTOM BRAIN: {c_mot}"
                    else:
                        sizing_kula = float(c_sz)
                except Exception as _e_cbf:
                    kula_ok = False
                    motivo_kula = f"VETO CUSTOM BRAIN Error: {_e_cbf}"
            elif "arbitro_ia" in globals() and callable(globals()["arbitro_ia"]) and TIENE_IA_CODIGO:
                try:
                    arb_res = globals()["arbitro_ia"](df.iloc[i], lado, entry, cur_sl_kula, float(tp))
                    if isinstance(arb_res, tuple):
                        a_ok = arb_res[0]
                        a_sz = arb_res[1] if len(arb_res) >= 2 and isinstance(arb_res[1], (int, float)) else 1.0
                        a_mot = arb_res[2] if len(arb_res) >= 3 else (arb_res[1] if len(arb_res) == 2 and isinstance(arb_res[1], str) else "ARBITRO_IA")
                    else:
                        a_ok = bool(arb_res)
                        a_sz = 1.0
                        a_mot = "ARBITRO_IA"
                    if not a_ok:
                        kula_ok = False
                        motivo_kula = f"VETO ARBITRO IA: {a_mot}"
                    else:
                        sizing_kula = float(a_sz)
                except Exception as _e_arb:
                    kula_ok = False
                    motivo_kula = f"VETO ARBITRO IA Error: {_e_arb}"

        if not pos_i:
            if kula_ok:
                fric_rt_pct = (comision * 2.0 + slippage * 2.0) * 100.0
                pnl_ia = (pnl_bruto - fric_rt_pct) * sizing_kula + fric_rt_pct
                trades_ia.append({"fecha": str(indices[i])[:16], "pnl_pct": pnl_ia, "reason": exit_reason, "oos": es_oos, "sl_dist_pct": sl_dist_pct, "sizing": sizing_kula})
                pos_i = True
                exit_i = exit_bar
            else:
                vetos_ia.append({"fecha": str(indices[i])[:16], "pnl_evitado": round(pnl_bruto, 2), "motivo": motivo_kula, "reason": exit_reason})

    df_m = pd.DataFrame(trades_math)
    df_i = pd.DataFrame(trades_ia)

    ticker_upper = ticker.upper()
    tf_infer = "5m" if ("5M" in ticker_upper or "_5M" in ticker_upper) else ("15m" if ("15M" in ticker_upper or "_15M" in ticker_upper) else ("1d" if ("1D" in ticker_upper or "_1D" in ticker_upper) else "4h"))

    res_m = evaluador.calcular_metricas(df_m, col_pnl_bruto="pnl_pct", timeframe=tf_infer)
    res_i = evaluador.calcular_metricas(df_i, col_pnl_bruto="pnl_pct", timeframe=tf_infer)

    # BLOQUE 3: AUDITORÍA CIEGA WALK-FORWARD (70% IS vs 30% OOS) - Calculado anticipadamente para usar en tabla
    df_m_is = df_m[~df_m["oos"]] if not df_m.empty else pd.DataFrame()
    df_m_oos = df_m[df_m["oos"]] if not df_m.empty else pd.DataFrame()
    r_m_is = evaluador.calcular_metricas(df_m_is, col_pnl_bruto="pnl_pct", timeframe=tf_infer)
    r_m_oos = evaluador.calcular_metricas(df_m_oos, col_pnl_bruto="pnl_pct", timeframe=tf_infer)

    df_i_is = df_i[~df_i["oos"]] if not df_i.empty else pd.DataFrame()
    df_i_oos = df_i[df_i["oos"]] if not df_i.empty else pd.DataFrame()
    r_i_is = evaluador.calcular_metricas(df_i_is, col_pnl_bruto="pnl_pct", timeframe=tf_infer)
    r_i_oos = evaluador.calcular_metricas(df_i_oos, col_pnl_bruto="pnl_pct", timeframe=tf_infer)
    r_is = r_i_is
    r_oos = r_i_oos

    span_dias = round((indices[-1] - indices[0]).total_seconds() / 86400.0, 1) if total > 1 else 0.0
    rango_str = f"{str(indices[0])[:10]} -> {str(indices[-1])[:10]} ({total} velas | {span_dias} días)"

    def _contar_salidas(df_t):
        if df_t.empty or "reason" not in df_t.columns:
            return "TP=0 | SL=0 | TRAIL=0 | TIEMPO=0"
        vc = df_t["reason"].value_counts().to_dict()
        return f"TP={vc.get('TP',0)} | SL={vc.get('SL',0)} | TRAIL={vc.get('TRAIL',0)} | TIEMPO={vc.get('TIME',0)}"

    print("\\n" + "=" * 90)
    print(f"   LAB: FÓRMULA MATEMÁTICA PURA vs. FÓRMULA ARBITRADA POR IA ANTIGRAVITY")
    print(f"   Activo: {ticker} | Mercado: {tipo_mercado} | Evaluación Dual Kula Balam")
    print(f"   Muestra: {rango_str}")
    print("=" * 90)
    print(f"{'MÉTRICA CUANTITATIVA':<32} | {'FÓRMULA PURA':<24} | {'FÓRMULA + IA':<24}")
    print("-" * 90)
    w_m = res_m.get('w_l_be', '')
    w_i = res_i.get('w_l_be', '')
    str_ops_m = f"{res_m['trades_totales']} ({w_m})" if w_m else str(res_m['trades_totales'])
    str_ops_i = f"{res_i['trades_totales']} ({w_i})" if w_i else str(res_i['trades_totales'])
    print(f"{'Operaciones Totales':<32} | {str_ops_m:<24} | {str_ops_i:<24}")
    print(f"{'Win Rate Neto':<32} | {res_m['win_rate_neto']}%{'':<18} | {res_i['win_rate_neto']}%{'':<18}")
    print(f"{'Profit Factor Neto':<32} | {res_m['pf_neto']:<24} | {res_i['pf_neto']:<24}")
    print(f"{'Ratio R:R Realizado':<32} | {res_m['rr_promedio_neto']:<24} | {res_i['rr_promedio_neto']:<24}")
    print(f"{'Retorno Neto Total':<32} | {res_m['retorno_neto_total_pct']}%{'':<18} | {res_i['retorno_neto_total_pct']}%{'':<18}")
    print(f"{'Máximo Drawdown':<32} | {res_m['max_drawdown_pct']}%{'':<18} | {res_i['max_drawdown_pct']}%{'':<18}")
    sort_m = res_m.get("sortino_ratio", 0.0)
    sort_i = res_i.get("sortino_ratio", 0.0)
    print(f"{'Sortino Ratio':<32} | {sort_m:<24} | {sort_i:<24}")
    mc_dd_m = res_m.get("mc_max_dd_95_pct", 0.0)
    mc_dd_i = res_i.get("mc_max_dd_95_pct", 0.0)
    mc_tag_m = f"{mc_dd_m}% ({'🟢≤8%' if mc_dd_m <= 8.0 else '🔴>8%'})"
    mc_tag_i = f"{mc_dd_i}% ({'🟢≤8%' if mc_dd_i <= 8.0 else '🔴>8%'})"
    print(f"{'Monte Carlo DD (95%)':<32} | {mc_tag_m:<24} | {mc_tag_i:<24}")
    suff_m = r_m_oos.get("sample_sufficiency", {})
    suff_i = r_i_oos.get("sample_sufficiency", {})
    suff_str_m = f"N={r_m_oos['trades_totales']} ({'🟢 OK' if suff_m.get('sample_sufficiency_ok') else '⚠️ Muestra Baja'})"
    suff_str_i = f"N={r_i_oos['trades_totales']} ({'🟢 OK' if suff_i.get('sample_sufficiency_ok') else '⚠️ Muestra Baja'})"
    print(f"{'Muestra OOS (N)':<32} | {suff_str_m:<24} | {suff_str_i:<24}")
    print(f"{'Max Daily DD (Peor Día ≤4.5%)':<32} | {res_m.get('max_daily_dd_pct', 0.0)}%{'':<18} | {res_i.get('max_daily_dd_pct', 0.0)}%{'':<18}")
    print(f"{'Racha Máx. Pérdidas (Streak)':<32} | {res_m.get('max_losing_streak', 0):<24} | {res_i.get('max_losing_streak', 0):<24}")
    fondeo_m = res_m.get('fondeo_dictamen', '❌ NO APTA')
    fondeo_i = res_i.get('fondeo_dictamen', '❌ NO APTA')
    fondeo_m_short = "✅ APTA (DD ≤ 8%)" if res_m.get("apta_fondeo") else ("❌ NO APTA" + (" (" + fondeo_m.split('(')[1] if '(' in fondeo_m else ""))
    fondeo_i_short = "✅ APTA (DD ≤ 8%)" if res_i.get("apta_fondeo") else ("❌ NO APTA" + (" (" + fondeo_i.split('(')[1] if '(' in fondeo_i else ""))
    print(f"{'Apta Cuentas Fondeo':<32} | {fondeo_m_short[:24]:<24} | {fondeo_i_short[:24]:<24}")
    print("-" * 90)
    dict_m_short = "✅ POSITIVA (Sin IA)" if res_m.get("aprobado") else "❌ DESCARTADA (Sin IA)"
    dict_i_short = "✅ POSITIVA (Con IA)" if res_i.get("aprobado") else ("⚠️ NEUTRA (Con IA)" if "NEUTRA" in str(res_i.get("dictamen", "")) else "❌ DESCARTADA (Con IA)")
    print(f"{'DICTAMEN':<32} | {dict_m_short:<24} | {dict_i_short:<24}")
    print(f"🏦 DICTAMEN FONDEO (PROP FIRM): [{res_i.get('prop_firm_semaforo', 'N/A')}]")
    print("=" * 90)
    print(f"[*] Resoluciones Pura : {_contar_salidas(df_m)}")
    print(f"[*] Resoluciones + IA : {_contar_salidas(df_i)}")

    # BLOQUE 3: AUDITORÍA CIEGA WALK-FORWARD (70% IS vs 30% OOS)
    print("\\n" + "-" * 90)
    print("   AUDITORÍA ANTI-SOBREAJUSTE WALK-FORWARD (70% IN-SAMPLE vs 30% OUT-OF-SAMPLE CIEGO)")
    print("-" * 90)
    w_m_is = f" ({r_m_is['w_l_be']})" if 'w_l_be' in r_m_is else ""
    w_i_is = f" ({r_i_is['w_l_be']})" if 'w_i_is' in r_i_is else ""
    w_m_oos = f" ({r_m_oos['w_l_be']})" if 'w_l_be' in r_m_oos else ""
    w_i_oos = f" ({r_i_oos['w_l_be']})" if 'w_i_oos' in r_i_oos else ""
    print(f"   • IN-SAMPLE (70% Calibración)   : Sin IA: N={r_m_is['trades_totales']}{w_m_is} | PF={r_m_is['pf_neto']} | WR={r_m_is['win_rate_neto']}% | Ret={r_m_is['retorno_neto_total_pct']}%")
    print(f"                                     Con IA: N={r_i_is['trades_totales']}{w_i_is} | PF={r_i_is['pf_neto']} | WR={r_i_is['win_rate_neto']}% | Ret={r_i_is['retorno_neto_total_pct']}%")
    print(f"   • OUT-OF-SAMPLE (30% Ciego Real): Sin IA: N={r_m_oos['trades_totales']}{w_m_oos} | PF={r_m_oos['pf_neto']} | WR={r_m_oos['win_rate_neto']}% | Ret={r_m_oos['retorno_neto_total_pct']}%")
    print(f"                                     Con IA: N={r_i_oos['trades_totales']}{w_i_oos} | PF={r_i_oos['pf_neto']} | WR={r_i_oos['win_rate_neto']}% | Ret={r_i_oos['retorno_neto_total_pct']}%")
    print("-" * 90)

    # Balance de Vetos (Shadow Counterfactual)
    sl_evitados = [v for v in vetos_ia if v.get("pnl_evitado", 0.0) < -1e-6]
    tp_perdidos = [v for v in vetos_ia if v.get("pnl_evitado", 0.0) > 1e-6]
    empates_vetados = [v for v in vetos_ia if abs(v.get("pnl_evitado", 0.0)) <= 1e-6]
    cap_salvado_pct = sum(abs(v["pnl_evitado"]) for v in sl_evitados)
    gan_perdida_pct = sum(v["pnl_evitado"] for v in tp_perdidos)
    print(f"\\n[+] BALANCE DE VETOS DEL CEREBRO KULA (Total Señales Vetadas: {len(vetos_ia)}):")
    print(f"    - Pérdidas / Trampas evitadas (SL Ahorrado) : {len(sl_evitados)} (+{cap_salvado_pct:.2f}% de Drawdown evitado)")
    print(f"    - Ganancias sacrificadas por prudencia (TP) : {len(tp_perdidos)} (-{gan_perdida_pct:.2f}% de ganancia sacrificada)")
    print(f"    - Cierres neutros / empates vetados         : {len(empates_vetados)}")
    if vetos_ia:
        print("\\n[*] Muestra de Vetos del Cerebro Kula:")
        for v in vetos_ia[-3:]:
            print(f"    • {v['fecha']} [PnL evitado: {v['pnl_evitado']:+.2f}%] -> {v['motivo']}")
    print("\\n" + "=" * 90 + "\\n")

    if "--json" in sys.argv:
        import json as _json_mod
        res_eval = res_i if TIENE_IA else res_m
        dict_eval = dict_i_short if TIENE_IA else ("✅ POSITIVA (Sin IA)" if res_m.get("aprobado") else "❌ DESCARTADA (Sin IA)")
        payload_metricas = {
            "ticker": ticker,
            "dataset": ruta.name,
            "mercado": tipo_mercado,
            "trades_totales": int(res_eval.get("trades_totales", 0)),
            "win_rate_neto": float(res_eval.get("win_rate_neto", 0.0)),
            "pf_neto": float(res_eval.get("pf_neto", 0.0)),
            "rr_promedio_neto": float(res_eval.get("rr_promedio_neto", 0.0)),
            "retorno_neto_total_pct": float(res_eval.get("retorno_neto_total_pct", 0.0)),
            "max_drawdown_pct": float(res_eval.get("max_drawdown_pct", 0.0)),
            "sortino_ratio": float(res_eval.get("sortino_ratio", 0.0)),
            "mc_max_dd_95_pct": float(res_eval.get("mc_max_dd_95_pct", 0.0)),
            "monte_carlo": res_eval.get("monte_carlo", {}),
            "sample_sufficiency": r_oos.get("sample_sufficiency", {}),
            "oos_sortino_ratio": float(r_oos.get("sortino_ratio", 0.0)),
            "oos_mc_max_dd_95_pct": float(r_oos.get("mc_max_dd_95_pct", 0.0)),
            "dictamen": dict_eval,
            "is_pf": float(r_is.get("pf_neto", 0.0)),
            "is_wr": float(r_is.get("win_rate_neto", 0.0)),
            "is_trades": int(r_is.get("trades_totales", 0)),
            "oos_pf": float(r_oos.get("pf_neto", 0.0)),
            "oos_wr": float(r_oos.get("win_rate_neto", 0.0)),
            "oos_trades": int(r_oos.get("trades_totales", 0)),
            "oos_ret": float(r_oos.get("retorno_neto_total_pct", 0.0)),
            "vetos_ia": len(vetos_ia) if TIENE_IA else 0,
            "aprobado": bool(res_eval.get("aprobado", False)),
            "apta_fondeo": bool(res_eval.get("apta_fondeo", False)),
            "fondeo_dictamen": str(res_eval.get("fondeo_dictamen", "N/A"))
        }
        print("###JSON_METRICAS_INICIO###" + _json_mod.dumps(payload_metricas) + "###JSON_METRICAS_FIN###")

    if MODO_ESCALADO:
        trades_eval = trades_ia if (TIENE_IA and len(trades_ia) > 0) else trades_math
        saldo_slot = float(SLOT_CAPITAL)
        saldo_inicial = saldo_slot
        saldo_pico = saldo_slot
        saldo_min = saldo_slot
        max_dd_slot = 0.0
        racha_perdidas_max = 0
        racha_actual = 0
        trades_base = 0
        trades_esc = 0
        pnl_base_total = 0.0
        pnl_esc_total = 0.0
        pnl_is_total = 0.0
        pnl_oos_total = 0.0
        quiebra = False
        escalado_activo = False

        friccion_dec = evaluador.friccion_roundtrip

        historial_slot = []

        for t in trades_eval:
            if not escalado_activo and saldo_slot >= UMBRAL_ESCALADO:
                escalado_activo = True
            elif escalado_activo and saldo_slot < UMBRAL_DESESCALADO:
                escalado_activo = False

            riesgo_trade = RIESGO_ESCALADO if escalado_activo else RIESGO_BASE
            sl_dist_dec = max(float(t.get("sl_dist_pct", 1.8)) / 100.0, 0.005)
            perdida_sl_pct = sl_dist_dec + friccion_dec
            nocional = riesgo_trade / perdida_sl_pct

            ret_neto_dec = (float(t["pnl_pct"]) / 100.0) - friccion_dec
            pnl_usd = round(nocional * ret_neto_dec, 2)

            saldo_slot += pnl_usd
            if saldo_slot > saldo_pico:
                saldo_pico = saldo_slot
            if saldo_slot < saldo_min:
                saldo_min = saldo_slot

            dd_actual = ((saldo_pico - saldo_slot) / saldo_pico) * 100.0 if saldo_pico > 0 else 0.0
            if dd_actual > max_dd_slot:
                max_dd_slot = dd_actual

            if pnl_usd < 0:
                racha_actual += 1
                if racha_actual > racha_perdidas_max:
                    racha_perdidas_max = racha_actual
            else:
                racha_actual = 0

            if escalado_activo:
                trades_esc += 1
                pnl_esc_total += pnl_usd
            else:
                trades_base += 1
                pnl_base_total += pnl_usd

            if t.get("oos", False):
                pnl_oos_total += pnl_usd
            else:
                pnl_is_total += pnl_usd

            if saldo_slot <= 5.0:
                quiebra = True

            historial_slot.append({
                "fecha": t["fecha"],
                "riesgo": riesgo_trade,
                "nocional": round(nocional, 2),
                "pnl_usd": pnl_usd,
                "saldo": round(saldo_slot, 2),
                "motivo": t.get("reason", "N/A"),
                "oos": t.get("oos", False)
            })

        c1_ok = (saldo_min >= (saldo_inicial * 0.70)) and (max_dd_slot <= 28.0) and not quiebra
        df_oos_eval = pd.DataFrame([t for t in trades_eval if t.get("oos", False)])
        res_oos_eval = evaluador.calcular_metricas(df_oos_eval, col_pnl_bruto="pnl_pct") if not df_oos_eval.empty else {}
        pf_oos = res_oos_eval.get("pf_neto", 0.0)
        rr_oos = res_oos_eval.get("rr_promedio_neto", 0.0)
        c2_ok = (pf_oos >= 1.25) and (rr_oos >= 1.80) and (pnl_oos_total >= 0.0)
        c3_ok = saldo_pico >= UMBRAL_ESCALADO

        aprobado_escalado = c1_ok and c2_ok and c3_ok

        print("\\n" + "=" * 90)
        print("   LAB: AUDITORÍA CUANTITATIVA DE ESCALADO DE RIESGO EN SLOT (KULA BALAM ANTI-RUINA)")
        print(f"   Activo: {ticker} | Capital Semilla Slot: ${saldo_inicial:.2f} USD")
        print(f"   Riesgo Base: ${RIESGO_BASE:.2f} USD (2.0% del slot) -> Escalado: ${RIESGO_ESCALADO:.2f} USD (4.0% del slot)")
        print(f"   Umbral Activación: >= ${UMBRAL_ESCALADO:.2f} USD (+${UMBRAL_ESCALADO - saldo_inicial:.2f}) | Desescalado: < ${UMBRAL_DESESCALADO:.2f} USD")
        print("=" * 90)
        print(f"{'MÉTRICA DEL SLOT':<38} | {'VALOR SIMULADO':<22} | {'UMBRAL DE SEGURIDAD':<24}")
        print("-" * 90)
        print(f"{'Saldo Inicial Semilla':<38} | ${saldo_inicial:.2f} USD{'':<12} | Slot Operativo 1 de 4")
        print(f"{'Saldo Final Acumulado':<38} | ${saldo_slot:.2f} USD{'':<12} | {'Crecimiento Positivo' if saldo_slot > saldo_inicial else 'Pérdida Neta'}")
        print(f"{'Saldo Pico Máximo':<38} | ${saldo_pico:.2f} USD{'':<12} | Meta Escalado: >= ${UMBRAL_ESCALADO:.2f}")
        print(f"{'Saldo Mínimo (Valle)':<38} | ${saldo_min:.2f} USD{'':<12} | Supervivencia: >= ${saldo_inicial * 0.70:.2f}")
        print(f"{'Máximo Drawdown en Slot':<38} | {max_dd_slot:.2f}%{'':<16} | Tolerancia Máx: <= 28.00%")
        print(f"{'Racha Máx Pérdidas Consecutivas':<38} | {racha_perdidas_max} trades{'':<13} | Tolerancia: <= 8 trades")
        print(f"{'Trades en Riesgo Base ($' + f'{RIESGO_BASE:.2f})':<38} | {trades_base} trades (PnL: ${pnl_base_total:+.2f}) | Fase de Acumulación")
        print(f"{'Trades en Riesgo Escalado ($' + f'{RIESGO_ESCALADO:.2f})':<38} | {trades_esc} trades (PnL: ${pnl_esc_total:+.2f}) | Fase de Aceleración")
        print(f"{'PnL Tramo In-Sample (70%)':<38} | ${pnl_is_total:+.2f} USD{'':<12} | Calibración")
        print(f"{'PnL Tramo Out-of-Sample (30% Ciego)':<38} | ${pnl_oos_total:+.2f} USD{'':<12} | Ventaja Ciega (PF: {pf_oos})")
        print(f"{'Riesgo de Ruina / Margin Call':<38} | {'❌ QUIEBRA' if quiebra else '✅ CERO QUIEBRAS':<22} | 0 Tolerancia")
        print("-" * 90)
        c1_str = "✅ APROBADA" if c1_ok else f"❌ FALLIDA (Min: ${saldo_min:.2f} | DD: {max_dd_slot:.1f}%)"
        c2_str = "✅ APROBADA" if c2_ok else f"❌ FALLIDA (PF OOS: {pf_oos} | PnL: ${pnl_oos_total:+.2f})"
        c3_str = "✅ ACTIVADO" if c3_ok else f"⚠️ NO ACTIVADO (Pico ${saldo_pico:.2f} < ${UMBRAL_ESCALADO:.2f})"
        print(f"{'COMPUERTA 1: SUPERVIVENCIA & DD':<38} | {c1_str:<22} | Saldo mín >= ${saldo_inicial * 0.70:.2f} & DD <= 28%")
        print(f"{'COMPUERTA 2: ROBUSTEZ OOS CIEGA':<38} | {c2_str:<22} | PF OOS >= 1.25 & PnL OOS > 0")
        print(f"{'COMPUERTA 3: CAPACIDAD DE TRACCIÓN':<38} | {c3_str:<22} | Pico de ganancia >= ${UMBRAL_ESCALADO:.2f}")
        print("=" * 90)
        if aprobado_escalado:
            print(">> DICTAMEN DE AUDITORÍA: ✅ AUTORIZADO PARA ESCALAR EN KULA BALAM ($0.50 -> $1.00 USD)")
            print("   Fundamento: La estrategia demostró resistencia anti-ruina y solvencia OOS ciega.")
        elif c1_ok and not c3_ok:
            print(">> DICTAMEN DE AUDITORÍA: ⚠️ ESCALADO NO ACTIVADO (MANTENER RIESGO BASE EN $0.50 USD)")
            print("   Fundamento: El slot sobrevive sin riesgo de ruina, pero la estrategia aún no acumula los beneficios necesarios para financiar el salto.")
        else:
            print(">> DICTAMEN DE AUDITORÍA: ❌ BLOQUEADO POR RIESGO DE RUINA O FRICCIÓN")
            print("   Fundamento: El perfil de pérdidas o la degradación Out-of-Sample pondría en peligro la integridad del slot de $25 USD.")
        print("\\n" + "=" * 90 + "\\n")

if __name__ == '__main__':
    ruta = Path(sys.argv[1])
    df_raw = pd.read_parquet(ruta) if ruta.suffix == '.parquet' else pd.read_csv(ruta)
    df_prep = preparar_mercado(df_raw)
    ticker = ruta.stem.replace('binance_', '').replace('yf_', '')
    simular(df_prep, ticker=ticker)
'''
    return script

def resolver_dataset_por_codigo(code_math: str, ticker_solicitado: str = "") -> Tuple[str, str]:
    """
    Resuelve el dataset aplicable combinando la selección explícita del operador y el código.
    Prioridad:
    1. Selección Manual Explícita del Operador en el selector (si es distinta de AUTO): TIENE PRIORIDAD MÁXIMA.
    2. Variable declarada explícitamente en el código: DATASET = "..." o DATASET_OBJETIVO = "..."
    3. Auto-detección por tipo de estrategia (scalping -> yf_SPY_5m.parquet, 4h -> binance_ETH_USDT_4h.parquet)
    4. Blindaje / Veto: Si se intenta correr Bitcoin en temporalidad < 1H, redirige automáticamente a SPY 5M.
    """
    code_text = code_math or ""
    ticker_final = None
    motivo = ""

    # 1. Si el operador seleccionó manualmente un dataset (distinto de AUTO), se respeta con máxima prioridad
    if ticker_solicitado and ticker_solicitado.strip().upper() not in ["", "AUTO"] and (DATA_DIR / ticker_solicitado).exists():
        ticker_final = ticker_solicitado
        motivo = f"Seleccionado manualmente por el operador: '{ticker_final}'"

    # 2. Si está en AUTO o no existe, verificar si la fórmula declara explícitamente DATASET
    if not ticker_final:
        for linea in code_text.splitlines():
            linea_s = linea.strip()
            if any(linea_s.startswith(k) for k in ["DATASET =", "DATASET=", "DATASET_OBJETIVO =", "DATASET_OBJETIVO="]):
                val = linea_s.split("=")[1].strip().strip("'\"")
                if (DATA_DIR / val).exists():
                    ticker_final = val
                    motivo = f"Declarado explícitamente en la fórmula: '{val}'"
                    break
                for ext in [".parquet", ".csv"]:
                    if (DATA_DIR / f"{val}{ext}").exists():
                        ticker_final = f"{val}{ext}"
                        motivo = f"Declarado explícitamente en la fórmula: '{ticker_final}'"
                        break

    # 3. Si aún no está resuelto, inferir por características técnicas del código
    if not ticker_final:
        code_lower = code_text.lower()
        es_4h = "4h" in code_lower
        es_1h_plus = any(w in code_lower for w in ["1h", "4h", "1d", "diario", "adx_5", "rsi3_adx5", "swing", "keltner", "donchian_breakout", "squeeze"])
        es_scalping = any(w in code_lower for w in ["5m", "scalp", "donchian_scalp", "vwap_2sigma", "15m"]) and not es_1h_plus

        if es_4h:
            ticker_final = "binance_ETH_USDT_4h.parquet"
            motivo = "⚡ Auto-detección por código: Régimen 4H Tendencial -> Cripto Institucional ETH 4H (3 años)"
        elif es_1h_plus:
            ticker_final = "binance_ETH_USDT_1h.parquet"
            motivo = "⚡ Auto-detección por código: Régimen 1H/Macro -> Cripto Institucional ETH 1H (3 años)"
        elif es_scalping:
            ticker_final = "yf_SPY_5m.parquet"
            motivo = "⚡ Auto-detección por código: Scalping/Intradía -> TradFi SPY 5M (0.10% Round-Trip)"
        else:
            ticker_final = "binance_ETH_USDT_4h.parquet"
            motivo = "⚡ Auto-detección por defecto seguro: ETH 4H (3 años)"
            motivo = "⚡ Auto-detección por defecto seguro: ETH 4H (3 años)"

    # 3. Blindaje / Veto inviolable de Bitcoin en intradía (< 1H)
    if "btc" in ticker_final.lower() and any(tf in ticker_final.lower() for tf in ["5m", "15m", "1m", "3m"]):
        ticker_final = "yf_SPY_5m.parquet"
        motivo = "🛡️ VETO SISTÉMICO ACTIVO: Bitcoin está vetado en temporalidades < 1H por AGENTS.md. Redirigido automáticamente a SPY 5M."

    return ticker_final, motivo

class RunRequest(BaseModel):
    category: str = ""
    ticker: Optional[str] = "AUTO"
    code: Optional[str] = ""
    code_math: Optional[str] = ""
    code_ia: Optional[str] = ""
    code_testigo: Optional[str] = ""
    periodo: Optional[str] = "TODO" 
    nombre_estrategia: Optional[str] = ""

class ResolveDatasetRequest(BaseModel):
    code_math: Optional[str] = ""
    ticker: Optional[str] = "AUTO"

@app.post("/api/resolve_dataset")
def api_resolve_dataset(req: ResolveDatasetRequest):
    ticker_final, motivo = resolver_dataset_por_codigo(req.code_math or "", req.ticker or "AUTO")
    return {"dataset": ticker_final, "motivo": motivo}

@app.post("/api/run")
def run_backtest(req: RunRequest):
    ticker, motivo_ds = resolver_dataset_por_codigo(req.code_math or req.code or "", req.ticker)
    data_file = DATA_DIR / ticker
    if not data_file.exists():
        return {"output": "", "error": f"Dataset {ticker} no encontrado en el disco."}

    # Si viene formato modular (code_math con o sin code_ia / code_testigo)
    if req.code_math and req.code_math.strip():
        codigo_final = generar_script_ejecucion(
            req.code_math,
            req.code_ia or "",
            req.code_testigo or "",
            nombre_estrategia=getattr(req, "nombre_estrategia", "") or ""
        )
    else:
        codigo_final = req.code or ""

    if not codigo_final.strip():
        return {"output": "", "error": "No se recibió código para ejecutar."}

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(codigo_final)
        tmp_path = tmp.name

    try:
        cmd = [sys.executable, "-u", tmp_path, str(data_file)]
        if getattr(req, "periodo", None):
            cmd.append(str(req.periodo))

        # Inyectar PYTHONPATH para permitir 'from core.metrics import EvaluadorCuantitativo'
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BASE_DIR) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=40,
            env=env,
            cwd=str(BASE_DIR),
        )
        return {"output": res.stdout, "error": res.stderr}
    except subprocess.TimeoutExpired:
        return {"output": "", "error": "El script superó el tiempo límite de ejecución (40 segundos)."}
    except Exception as e:
        return {"output": "", "error": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ---------------------------------------------------------
# 4.3.1 VALIDACIÓN WALK-FORWARD DESLIZANTE (ROLLING WFO)
# ---------------------------------------------------------
class WfoRollingRequest(BaseModel):
    ticker: Optional[str] = "AUTO"
    code_math: str
    code_ia: Optional[str] = ""
    n_windows: int = 5
    is_ratio: float = 0.70
    warmup_bars: int = 250


@app.post("/api/lab/evaluar_wfo_rolling")
def api_evaluar_wfo_rolling(req: WfoRollingRequest):
    if not req.code_math or not req.code_math.strip():
        return {
            "wfo_valid": False,
            "reason": "Código matemático requerido para WFO Rodante.",
            "detail": "Código matemático requerido para WFO Rodante.",
            "n_windows": 0,
            "wfe_ratio": 0.0,
            "positive_oos_windows": 0,
            "consistency_pct": 0.0,
            "wfo_passed": False,
            "windows": [],
            "ticker": req.ticker or "AUTO",
            "resumen_texto": "❌ Código matemático requerido para WFO Rodante.",
        }

    ticker, motivo_ds = resolver_dataset_por_codigo(req.code_math, req.ticker or "AUTO")
    data_file = DATA_DIR / ticker
    if not data_file.exists():
        return {
            "wfo_valid": False,
            "reason": f"Dataset {ticker} no encontrado.",
            "detail": f"Dataset {ticker} no encontrado.",
            "n_windows": 0,
            "wfe_ratio": 0.0,
            "positive_oos_windows": 0,
            "consistency_pct": 0.0,
            "wfo_passed": False,
            "windows": [],
            "ticker": ticker,
            "resumen_texto": f"❌ Dataset {ticker} no encontrado.",
        }

    try:
        import sys
        import math
        from pathlib import Path
        from typing import Dict, Tuple, Optional, Any, List, Union, Callable

        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        if str(BASE_DIR.parent) not in sys.path:
            sys.path.insert(0, str(BASE_DIR.parent))

        import pandas as pd
        import numpy as np

        try:
            from core.metrics import EvaluadorCuantitativo
            from core.wfo_rolling import run_rolling_wfo
        except ImportError:
            from backtest_lab.core.metrics import EvaluadorCuantitativo
            from backtest_lab.core.wfo_rolling import run_rolling_wfo

        df_raw = pd.read_parquet(data_file) if data_file.suffix == ".parquet" else pd.read_csv(data_file)

        def check_universal_wick_veto_local(df_slice: pd.DataFrame, side: str, max_wick_ratio: float = 0.50):
            if len(df_slice) < 1:
                return None
            last_c = df_slice.iloc[-1]
            high = float(last_c.get("high", 0.0))
            low = float(last_c.get("low", 0.0))
            open_p = float(last_c.get("open", 0.0))
            close_p = float(last_c.get("close", 0.0))
            total_rng = high - low
            if total_rng <= 1e-8:
                return None
            if str(side).upper() == "LONG":
                upper_wick = high - max(open_p, close_p)
                if upper_wick / total_rng >= max_wick_ratio:
                    return f"VETO UNIVERSAL MECHA: Mecha superior {upper_wick/total_rng:.1%} >= {max_wick_ratio:.0%}"
            elif str(side).upper() == "SHORT":
                lower_wick = min(open_p, close_p) - low
                if lower_wick / total_rng >= max_wick_ratio:
                    return f"VETO UNIVERSAL MECHA: Mecha inferior {lower_wick/total_rng:.1%} >= {max_wick_ratio:.0%}"
            return None

        ns: dict = {
            "pd": pd,
            "np": np,
            "math": math,
            "sys": sys,
            "Path": Path,
            "Dict": Dict,
            "Tuple": Tuple,
            "Optional": Optional,
            "Any": Any,
            "List": List,
            "Union": Union,
            "Callable": Callable,
            "check_universal_wick_veto_local": check_universal_wick_veto_local,
            "__builtins__": __builtins__,
        }
        exec(req.code_math, ns)
        if req.code_ia and req.code_ia.strip():
            exec(req.code_ia, ns)
        elif "ARBITRO_IA" in ns and isinstance(ns["ARBITRO_IA"], str):
            arb_nom = ns["ARBITRO_IA"].strip()
            arb_path = ESTRATEGIAS_IA_DIR / arb_nom
            if arb_path.exists():
                try:
                    exec(arb_path.read_text(encoding="utf-8"), ns)
                except Exception:
                    pass

        if "formula_matematica" not in ns:
            return {
                "wfo_valid": False,
                "reason": "La estrategia debe definir def formula_matematica(df, i).",
                "detail": "La estrategia debe definir def formula_matematica(df, i).",
                "n_windows": 0,
                "wfe_ratio": 0.0,
                "positive_oos_windows": 0,
                "consistency_pct": 0.0,
                "wfo_passed": False,
                "windows": [],
                "ticker": ticker,
                "resumen_texto": "❌ La estrategia debe definir def formula_matematica(df, i).",
            }

        formula_fn = ns["formula_matematica"]
        arbitro_fn = ns.get("arbitro_ia")
        custom_fn = ns.get("custom_brain_filter")
        max_hold = int(ns.get("MAX_BARS_HOLD", 48))

        # Preparar indicadores base sobre el dataset completo una sola vez (causal con .shift(1))
        df = df_raw.copy()
        df.columns = [str(c).lower() for c in df.columns]
        if not isinstance(df.index, pd.DatetimeIndex):
            col_t = next((c for c in ["datetime", "timestamp", "date", "time"] if c in df.columns), None)
            if col_t:
                s_t = df[col_t]
                unit = "ms" if (pd.api.types.is_numeric_dtype(s_t) and float(s_t.iloc[0]) > 1e11) else "s"
                df[col_t] = pd.to_datetime(s_t, unit=unit, utc=True) if pd.api.types.is_numeric_dtype(s_t) else pd.to_datetime(s_t, utc=True)
                df.set_index(col_t, inplace=True)
        df = df.sort_index()
        for c_name in ["open", "high", "low", "close", "volume"]:
            if c_name in df.columns:
                df[c_name] = df[c_name].astype(float)
        prev_c = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_c).abs(), (df["low"] - prev_c).abs()], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean().shift(1).bfill()
        if "volume" in df.columns and df["volume"].sum() > 0:
            df["vol_sma"] = df["volume"].rolling(20).mean().shift(1).bfill()
            df["rvol"] = df["volume"] / (df["vol_sma"] + 1e-9)
        else:
            df["vol_sma"] = 1000.0
            df["rvol"] = 1.3
        df["rvol_3_prev"] = df["rvol"].shift(1).rolling(3, min_periods=1).mean().fillna(1.0)
        rango = (df["high"] - df["low"]).replace(0, 1e-9)
        techo = df[["open", "close"]].max(axis=1)
        suelo = df[["open", "close"]].min(axis=1)
        df["mecha_superior_pct"] = ((df["high"] - techo) / rango) * 100.0
        df["mecha_inferior_pct"] = ((suelo - df["low"]) / rango) * 100.0
        df["cuerpo_pct"] = ((df["close"] - df["open"]).abs() / rango) * 100.0
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_100"] = df["close"].ewm(span=100, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
        df["dist_ema_atrs"] = (df["close"] - df["ema_50"]).abs() / (df["atr"] + 1e-9)
        df["dist_ema200_atrs"] = (df["close"] - df["ema_200"]) / (df["atr"] + 1e-9)
        df["ema_200_slope"] = (df["ema_200"] - df["ema_200"].shift(5)) / (df["atr"] + 1e-9)
        cambio_neto_20 = (df["close"] - df["close"].shift(20)).abs()
        volatilidad_ruta_20 = df["close"].diff().abs().rolling(20).sum()
        df["er_20"] = (cambio_neto_20 / (volatilidad_ruta_20 + 1e-9)).fillna(0.3)

        # Indicadores complementarios: Bandas de Bollinger (20, 2)
        sma20 = df["close"].shift(1).rolling(20).mean().bfill()
        std20 = df["close"].shift(1).rolling(20).std().bfill()
        df["bb_mid"] = sma20
        df["bb_up"] = sma20 + 2.0 * std20
        df["bb_low"] = sma20 - 2.0 * std20
        df["bb_width"] = (4.0 * std20) / (df["atr"] + 1e-9)

        # Canales de Donchian (20 y 30)
        df["donchian_high_20"] = df["high"].shift(1).rolling(20).max().bfill()
        df["donchian_low_20"] = df["low"].shift(1).rolling(20).min().bfill()
        df["donchian_high_30"] = df["high"].shift(1).rolling(30).max().bfill()
        df["donchian_low_30"] = df["low"].shift(1).rolling(30).min().bfill()

        # RSI (14)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(14).mean()
        loss = ((-delta.where(delta < 0, 0.0))).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df["rsi"] = (100.0 - (100.0 / (1.0 + rs))).shift(1).bfill().fillna(50.0)

        # MACD (12, 26, 9)
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd_line"] = (ema_12 - ema_26).shift(1).bfill()
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd_line"] - df["macd_signal"]

        # ADX (14)
        up_move = df["high"] - df["high"].shift(1)
        down_move = df["low"].shift(1) - df["low"]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr_adx = tr.replace(0, 1e-9)
        plus_di = 100.0 * (pd.Series(plus_dm, index=df.index).rolling(14).mean() / tr_adx)
        minus_di = 100.0 * (pd.Series(minus_dm, index=df.index).rolling(14).mean() / tr_adx)
        dx = (100.0 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9)).fillna(25.0)
        df["adx"] = dx.rolling(14).mean().shift(1).bfill().fillna(25.0)
        df["plus_di"] = plus_di.shift(1).bfill().fillna(25.0)
        df["minus_di"] = minus_di.shift(1).bfill().fillna(25.0)

        t_up = ticker.upper()
        if any(fx in t_up for fx in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD"]):
            comision, slippage = 0.0001, 0.00005
        elif any(st in t_up for st in ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "AVGO", "GOOGL", "AMZN", "META", "TSLA"]):
            comision, slippage = 0.0002, 0.0003
        else:
            comision, slippage = 0.0008, 0.0005
        evaluador = EvaluadorCuantitativo(comision_pct=comision, slippage_pct=slippage)

        def _eval_window(df_slice: pd.DataFrame, start_rel: int, end_rel: int) -> dict:
            trades = []
            pos_open = False
            exit_idx = -1
            n_slice = len(df_slice)
            lim = min(end_rel, n_slice - 1)
            for i in range(max(50, start_rel), lim):
                if pos_open and i >= exit_idx:
                    pos_open = False
                if pos_open:
                    continue
                try:
                    res_cand = formula_fn(df_slice, i)
                except Exception:
                    continue

                if isinstance(res_cand, (tuple, list)):
                    if len(res_cand) >= 4:
                        cand, lado, sl, tp = res_cand[0], res_cand[1], res_cand[2], res_cand[3]
                    elif len(res_cand) == 3:
                        cand, sl, tp = res_cand[0], res_cand[1], res_cand[2]
                        lado = "LONG"
                    else:
                        cand = res_cand[0] if len(res_cand) > 0 else False
                        lado, sl, tp = "LONG", 0.0, 0.0
                else:
                    cand = bool(res_cand)
                    lado, sl, tp = "LONG", 0.0, 0.0
                if not cand:
                    continue
                entry = float(df_slice.iloc[i + 1]["open"]) if i + 1 < n_slice else float(df_slice.iloc[i]["close"])
                sz = 1.0
                if callable(custom_fn):
                    try:
                        cbf = custom_fn(df_slice, i, lado, entry, float(sl), float(tp))
                        ok = cbf[0] if isinstance(cbf, tuple) else bool(cbf)
                        if not ok:
                            continue
                    except Exception:
                        continue
                elif callable(arbitro_fn):
                    try:
                        arb = arbitro_fn(df_slice.iloc[i], lado, entry, float(sl), float(tp))
                        ok = arb[0] if isinstance(arb, tuple) else bool(arb)
                        if not ok:
                            continue
                        if isinstance(arb, tuple) and len(arb) >= 2 and isinstance(arb[1], (int, float)):
                            sz = float(arb[1])
                    except Exception:
                        continue

                p_ex = float(df_slice["close"].iloc[min(i + max_hold, n_slice - 1)])
                ex_b = min(i + max_hold, n_slice - 1)
                for j in range(i + 1, min(i + max_hold + 1, n_slice)):
                    oj, hj, lj = float(df_slice["open"].iloc[j]), float(df_slice["high"].iloc[j]), float(df_slice["low"].iloc[j])
                    if lado == "LONG":
                        if lj <= float(sl):
                            p_ex, ex_b = min(oj, float(sl)), j
                            break
                        if hj >= float(tp):
                            p_ex, ex_b = max(oj, float(tp)), j
                            break
                    else:
                        if hj >= float(sl):
                            p_ex, ex_b = max(oj, float(sl)), j
                            break
                        if lj <= float(tp):
                            p_ex, ex_b = min(oj, float(tp)), j
                            break
                fric_rt_pct = (comision * 2.0 + slippage * 2.0) * 100.0
                pnl_raw_pct = ((p_ex - entry) / entry) * 100.0 if lado == "LONG" else ((entry - p_ex) / entry) * 100.0
                pnl_b = (pnl_raw_pct - fric_rt_pct) * sz + fric_rt_pct
                trades.append({"pnl_pct": pnl_b})
                pos_open = True
                exit_idx = ex_b

            m = evaluador.calcular_metricas(pd.DataFrame(trades), col_pnl_bruto="pnl_pct")
            return {
                "net_return_pct": float(m.get("retorno_neto_total_pct", 0.0)),
                "trades_count": int(m.get("trades_totales", 0)),
                "profit_factor": float(m.get("pf_neto", 0.0)),
            }

        wfo_res = run_rolling_wfo(
            df=df,
            eval_window_fn=_eval_window,
            n_windows=int(req.n_windows or 5),
            is_ratio=float(req.is_ratio or 0.70),
            warmup_bars=int(req.warmup_bars or 250),
        )

        lineas = [
            "=" * 90,
            f"   🔄 AUDITORÍA WALK-FORWARD DESLIZANTE (ROLLING WFO · {wfo_res.get('n_windows', 0)} VENTANAS)",
            f"   Dataset: {ticker} | Ratio IS/OOS: {int((req.is_ratio or 0.70)*100)}%/{int((1-(req.is_ratio or 0.70))*100)}% | Warmup: {req.warmup_bars} velas",
            "=" * 90,
        ]
        if not wfo_res.get("wfo_valid"):
            lineas.append(f"   ❌ WFO INVÁLIDO: {wfo_res.get('reason')}")
        else:
            lineas.append(f"   {'VENTANA':<10} | {'VELAS IS':<10} | {'RET IS (%)':<12} | {'VELAS OOS':<10} | {'RET OOS (%)':<12} | {'PF OOS':<8} | {'TRADES OOS':<10}")
            lineas.append("   " + "-" * 84)
            for w in wfo_res.get("windows", []):
                lineas.append(
                    f"   #{w['window_index']:<9} | {w['is_bars']:<10} | {w['is_return_pct']:>+10.2f}% | {w['oos_bars']:<10} | {w['oos_return_pct']:>+10.2f}% | {w['oos_pf']:<8.2f} | {w['oos_trades']:<10}"
                )
            lineas.append("   " + "-" * 84)
            est_wfo = "✅ ROBUSTA (WFE >= 0.50 y Consistencia >= 60%)" if wfo_res.get("wfo_passed") else "❌ FRÁGIL / SOBREAJUSTADA"
            lineas.append(f"   • Walk-Forward Efficiency (WFE) : {wfo_res.get('wfe_ratio', 0.0):.2f} (Exigido >= 0.50)")
            lineas.append(f"   • Consistencia Ventanas OOS (+) : {wfo_res.get('positive_oos_windows', 0)}/{wfo_res.get('n_windows', 0)} ({wfo_res.get('consistency_pct', 0.0)}%)")
            lineas.append(f"   • DICTAMEN WFO RODANTE          : {est_wfo}")
        lineas.append("=" * 90)

        wfo_res["ticker"] = ticker
        wfo_res["resumen_texto"] = "\n".join(lineas)
        return wfo_res

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        lineas_err = [
            "=" * 90,
            "   🔄 AUDITORÍA WALK-FORWARD DESLIZANTE (ROLLING WFO)",
            "=" * 90,
            f"   ❌ ERROR EN EJECUCIÓN WFO RODANTE: {str(e)}",
            "=" * 90,
        ]
        return {
            "wfo_valid": False,
            "reason": str(e),
            "detail": str(e),
            "traceback": tb,
            "n_windows": 0,
            "wfe_ratio": 0.0,
            "positive_oos_windows": 0,
            "consistency_pct": 0.0,
            "wfo_passed": False,
            "windows": [],
            "ticker": req.ticker or "AUTO",
            "resumen_texto": "\n".join(lineas_err),
        }

# ---------------------------------------------------------
# 4.4 AUDITORÍA DE ESCALADO CUANTITATIVO POR SLOTS
# ---------------------------------------------------------
class AuditEscaladoRequest(BaseModel):
    category: Optional[str] = "datos_historicos"
    ticker: Optional[str] = "AUTO"
    code_math: Optional[str] = ""
    code_ia: Optional[str] = ""
    code_testigo: Optional[str] = ""
    slot_capital: Optional[float] = 25.0
    riesgo_base: Optional[float] = 0.50
    riesgo_escalado: Optional[float] = 1.00
    umbral_escalado: Optional[float] = 35.0
    umbral_desescalado: Optional[float] = 30.0
    nombre_estrategia: Optional[str] = ""

@app.post("/api/auditar_escalado")
def api_auditar_escalado(req: AuditEscaladoRequest):
    ticker, motivo_ds = resolver_dataset_por_codigo(req.code_math or "", req.ticker or "AUTO")
    data_file = DATA_DIR / ticker
    if not data_file.exists():
        return {"output": "", "error": f"Dataset {ticker} no encontrado en el disco."}

    if not req.code_math or not req.code_math.strip():
        return {"output": "", "error": "No se recibió código de fórmula matemática para auditar."}

    codigo_final = generar_script_ejecucion(
        code_math=req.code_math,
        code_ia=req.code_ia or "",
        code_testigo=req.code_testigo or "",
        modo_escalado=True,
        slot_capital=float(req.slot_capital if req.slot_capital is not None else 25.0),
        riesgo_base=float(req.riesgo_base if req.riesgo_base is not None else 0.50),
        riesgo_escalado=float(req.riesgo_escalado if req.riesgo_escalado is not None else 1.00),
        umbral_escalado=float(req.umbral_escalado if req.umbral_escalado is not None else 35.0),
        umbral_desescalado=float(req.umbral_desescalado if req.umbral_desescalado is not None else 30.0),
        nombre_estrategia=getattr(req, "nombre_estrategia", "") or "",
    )

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(codigo_final)
        tmp_path = tmp.name

    try:
        cmd = [sys.executable, "-u", tmp_path, str(data_file)]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BASE_DIR) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45,
            env=env,
            cwd=str(BASE_DIR),
        )
        return {"output": res.stdout, "error": res.stderr}
    except subprocess.TimeoutExpired:
        return {"output": "", "error": "La auditoría de escalado superó el tiempo límite (45 segundos)."}
    except Exception as e:
        return {"output": "", "error": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ---------------------------------------------------------
# 4.5 OPTIMIZADOR AUTÓNOMO LOCAL (GRID SEARCH)
# ---------------------------------------------------------
@app.post("/api/optimize")
def optimize_strategy(req: RunRequest):
    ticker, motivo_ds = resolver_dataset_por_codigo(req.code_math or req.code or "", req.ticker)
    data_file = DATA_DIR / ticker
    if not data_file.exists():
        return {"output": "", "error": f"Dataset {ticker} no encontrado en el disco."}

    try:
        try:
            from backtest_lab.optimizador_autonomo import ejecutar_barrido
        except ImportError:
            from optimizador_autonomo import ejecutar_barrido

        code_low = (req.code_math or req.code or "").lower()
        fam_forzada = None
        if "_bb_up" in code_low or "bollinger" in code_low or "squeeze_dual" in code_low:
            fam_forzada = "BB_SQUEEZE_DUAL"
        elif "donchian" in code_low:
            fam_forzada = "DONCHIAN_SQUEEZE"

        res = ejecutar_barrido(ticker, guardar_ganador=False, familia_forzada=fam_forzada)
        
        lineas = []
        lineas.append("=" * 90)
        lineas.append("   LAB: RESULTADOS DEL BARRIDO PARAMÉTRICO AUTÓNOMO (GRID SEARCH LOCAL)")
        lineas.append(f"   Activo: {ticker} | Combinaciones Evaluadas: {res['total_evaluadas']} | Rentables: {res['ganadoras_filtradas']}")
        lineas.append(f"   Motivo: {motivo_ds}")
        lineas.append("=" * 90)
        lineas.append(f"{'#':<4} | {'PF NETO':<9} | {'WIN RATE':<10} | {'TRADES':<8} | {'MAX DD':<8} | PARÁMETROS CALIBRADOS")
        lineas.append("-" * 90)
        
        for idx, item in enumerate(res.get("top_5", []), 1):
            p = item["parametros"]
            m = item["metricas"]
            m_oos = item.get("metricas_oos", {})
            if "descripcion" in p:
                params_str = p["descripcion"]
            elif "sigma" in p:
                params_str = f"Sigma: {p['sigma']} | RVOL: {p['rvol']}x | Mecha: {p['wick_min']}% | SL: {p['sl_mult']} ATR | TP: {p['rr_target']}x"
            else:
                params_str = ", ".join(f"{k}={v}" for k, v in p.items())
            oos_tag = f" [OOS PF={m_oos.get('pf_neto', '-')}]" if m_oos else ""
            lineas.append(f"#{idx:<3} | {m['pf_neto']:<9} | {str(m['win_rate_neto'])+'%':<10} | {m['trades_totales']:<8} | {str(m['max_drawdown_pct'])+'%':<8} | {params_str}{oos_tag}")
            
        lineas.append("=" * 90)
        if res.get("califica_institucional"):
            lineas.append("[🏆] VALLA INSTITUCIONAL + WALK-FORWARD OOS SUPERADA:")
            lineas.append("     La familia evaluada superó la validación ciega en IS (70%) y OOS (30%).")
            lineas.append("     >> Código cargado en memoria listo para auditar o guardar vía 'Guardar en Carpeta Lab'.")
        else:
            lineas.append("[🛡️] PROTECCIÓN DE HISTORIAL ACTIVA (Valla Institucional No Superada):")
            lineas.append(f"     Motivo: {res.get('motivo_no_guardado', 'Muestra insuficiente o métricas por debajo del estándar.')}")
            lineas.append("     >> NO se guardó ninguna fórmula para no contaminar tus fórmulas oficiales con procesos mediocres.")
            lineas.append("     (Los datos crudos de las combinaciones quedaron registrados en 'estrategias_ganadoras.json')")
        lineas.append("=" * 90)
        
        return {
            "output": "\n".join(lineas),
            "error": "",
            "califica_institucional": bool(res.get("califica_institucional", False)),
            "archivo_guardado": res.get("archivo_guardado"),
            "codigo_optimizado": res.get("codigo_optimizado")
        }
    except Exception as e:
        return {"output": "", "error": f"Error en la optimización autónoma: {str(e)}"}

# ---------------------------------------------------------
# 4.6 GENERADOR DE ESTRATEGIAS CUANTITATIVAS CON IA (PROMPT-TO-BACKTEST)
# ---------------------------------------------------------
class GenerarEstrategiaRequest(BaseModel):
    prompt: str
    motor: Optional[str] = "auto"
    api_key: Optional[str] = ""
    ticker: Optional[str] = "AUTO"
    code_math_existente: Optional[str] = ""
    code_ia_existente: Optional[str] = ""

@app.post("/api/generar_estrategia_ia")
def api_generar_estrategia_ia(req: GenerarEstrategiaRequest):
    try:
        try:
            from backtest_lab.generador_ia import sintetizar_estrategia
        except ImportError:
            from generador_ia import sintetizar_estrategia

        res = sintetizar_estrategia(
            prompt=req.prompt,
            motor=req.motor or "auto",
            api_key=req.api_key or "",
            ticker_hint=req.ticker or "AUTO",
            code_math_existente=req.code_math_existente or "",
            code_ia_existente=req.code_ia_existente or "",
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla en la síntesis de estrategia IA: {str(e)}")

# ---------------------------------------------------------
# 4.7 SCREENING GRID: BARRIDO MASIVO MULTI-ACTIVO & MULTI-TEMPORALIDAD
# ---------------------------------------------------------
class ScreeningGridRequest(BaseModel):
    code_math: str
    code_ia: Optional[str] = ""
    universo: Optional[str] = "todos"
    top_n: Optional[int] = 15
    max_workers: Optional[int] = 4

@app.post("/api/screening_grid")
def api_screening_grid(req: ScreeningGridRequest):
    if not req.code_math or not req.code_math.strip():
        return {
            "universo": req.universo or "todos",
            "total_evaluados": 0,
            "aptos": 0,
            "ranking": [],
            "resumen_texto": "No se recibió código de fórmula matemática para evaluar."
        }

    try:
        try:
            from backtest_lab.screening_grid import ejecutar_screening_grid
        except ImportError:
            from screening_grid import ejecutar_screening_grid

        res = ejecutar_screening_grid(
            code_math=req.code_math,
            code_ia=req.code_ia or "",
            universo=req.universo or "todos",
            top_n=req.top_n or 15,
            max_workers=req.max_workers or 4
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla en el screening grid: {str(e)}")

# ---------------------------------------------------------
# 4.8 ADAPTADOR E INGESTA DE ESTRATEGIAS FREQTRADE
# ---------------------------------------------------------
class FreqtradeAdaptRequest(BaseModel):
    codigo: str
    activo: Optional[str] = "AUTO"

@app.get("/api/freqtrade/biblioteca")
def api_freqtrade_biblioteca():
    try:
        try:
            from backtest_lab.adaptador_freqtrade import listar_biblioteca_freqtrade
        except ImportError:
            from adaptador_freqtrade import listar_biblioteca_freqtrade
        return listar_biblioteca_freqtrade()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla al listar biblioteca Freqtrade: {str(e)}")

@app.get("/api/freqtrade/cargar/{archivo}")
def api_freqtrade_cargar(archivo: str):
    try:
        try:
            from backtest_lab.adaptador_freqtrade import BIBLIOTECA_DIR, adaptar_codigo_freqtrade
        except ImportError:
            from adaptador_freqtrade import BIBLIOTECA_DIR, adaptar_codigo_freqtrade

        p = BIBLIOTECA_DIR / archivo
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail=f"Estrategia Freqtrade '{archivo}' no encontrada en disco.")
        
        raw_code = p.read_text(encoding="utf-8")
        res = adaptar_codigo_freqtrade(raw_code)
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla al adaptar estrategia Freqtrade: {str(e)}")

@app.post("/api/freqtrade/adaptar")
def api_freqtrade_adaptar(req: FreqtradeAdaptRequest):
    if not req.codigo or not req.codigo.strip():
        raise HTTPException(status_code=400, detail="No se recibió código de estrategia Freqtrade para adaptar.")

    try:
        try:
            from backtest_lab.adaptador_freqtrade import adaptar_codigo_freqtrade
        except ImportError:
            from adaptador_freqtrade import adaptar_codigo_freqtrade

        res = adaptar_codigo_freqtrade(req.codigo, activo_hint=req.activo or "AUTO")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla en la adaptación de estrategia Freqtrade: {str(e)}")

# ---------------------------------------------------------
# 4.8 TORNEO DE PODA ITERATIVA Y ENSAMBLE CAMPEÓN (CHALLENGER LADDER)
# ---------------------------------------------------------
class TorneoEnsembleRequest(BaseModel):
    dataset: Optional[str] = "binance_ETH_USDT_4h.parquet"
    max_batch_size: Optional[int] = 5

@app.post("/api/ensemble/torneo_poda")
def api_ensemble_torneo_poda(req: TorneoEnsembleRequest):
    try:
        try:
            from backtest_lab.core.ensemble_pruner import ejecutar_torneo_poda
        except ImportError:
            from core.ensemble_pruner import ejecutar_torneo_poda

        res = ejecutar_torneo_poda(
            dataset_name=req.dataset or "binance_ETH_USDT_4h.parquet",
            max_batch_size=int(req.max_batch_size or 5)
        )
        return res
    except Exception as e:
        logger.error(f"Falla en el Torneo de Poda: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Falla en el Torneo de Poda: {str(e)}")

# ---------------------------------------------------------
# 4.9 PROMOCIÓN EN VIVO AL TRADER DAEMON (FASE 4)
# ---------------------------------------------------------
class PromocionProduccionRequest(BaseModel):
    ticker: Optional[str] = "AUTO"
    code_math: str
    code_ia: Optional[str] = ""
    nombre: Optional[str] = "estrategia_promovida.py"
    slot_id: Optional[int] = 1
    confianza: Optional[int] = 85
    justificacion: Optional[str] = ""
    destino: Optional[str] = "principal"  # 'principal', 'operador_presente', 'para_testear_ganadoras'
    mc_max_dd_95_pct: Optional[float] = None

def mapear_dataset_a_simbolo(dataset_o_ticker: str) -> str:
    s = (dataset_o_ticker or "").strip()
    if not s or s.upper() == "AUTO":
        return "SOL/USDT"
    
    # Limpiar prefijos y sufijos parquet
    limpio = re.sub(r"^(binance_|yf_)", "", s, flags=re.IGNORECASE)
    limpio = re.sub(r"(_(1m|3m|5m|15m|30m|1h|2h|4h|1d))?\.parquet$", "", limpio, flags=re.IGNORECASE)
    
    if "_USDT" in limpio.upper():
        return limpio.upper().replace("_", "/")
    
    if limpio.upper() in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"]:
        return f"{limpio.upper()}=X"
        
    return limpio.upper()

@app.post("/api/promover_a_produccion")
def api_promover_a_produccion(req: PromocionProduccionRequest):
    if not req.code_math or not req.code_math.strip():
        raise HTTPException(status_code=400, detail="No se recibió código de fórmula matemática para promover.")

    if req.mc_max_dd_95_pct is not None and float(req.mc_max_dd_95_pct) > 8.0:
        raise HTTPException(
            status_code=400,
            detail=f"Promoción rechazada por Compuerta Institucional: Drawdown Monte Carlo al 95% ({float(req.mc_max_dd_95_pct):.2f}%) supera el límite máximo permitido de 8.0%."
        )

    try:
        # 1. Resolver dataset y mapear a símbolo oficial del broker/daemon
        ticker_ds, _ = resolver_dataset_por_codigo(req.code_math, req.ticker or "AUTO")
        simbolo = mapear_dataset_a_simbolo(ticker_ds)
        slot_id = max(1, min(4, int(req.slot_id or 1)))
        confianza = max(75, min(100, int(req.confianza or 85)))
        ds_low = ticker_ds.lower()
        tf = "4h" if "4h" in ds_low else ("1d" if "1d" in ds_low else ("1h" if "1h" in ds_low else ("15m" if "15m" in ds_low else "5m")))
        simbolo_slug = simbolo.replace('/', '_').replace('=X', '').lower()

        # Determinación de base_name no colisionante y descriptivo
        raw_name = Path(req.nombre or "estrategia_promovida.py").stem.strip()
        generic_names = {"", "estrategia_promovida", "estrategia_validada", "tendencia_optimizada_auto", "tendencia_optimizada_experimental", "formula_math"}
        if raw_name.lower() in generic_names:
            cod_upper = req.code_math.upper()
            if "DONCHIAN" in cod_upper:
                fam = "donchian_breakout"
            elif "SQUEEZE" in cod_upper or "BOLLINGER" in cod_upper:
                fam = "squeeze_dual"
            elif "RSI" in cod_upper:
                fam = "rsi_momentum"
            elif "VWAP" in cod_upper:
                fam = "reversion_vwap"
            else:
                fam = "tendencia_optimizada"
            base_name = f"{fam}_{simbolo_slug}_{tf}"
        else:
            clean_chars = [c if (c.isalnum() or c in ('_', '-')) else '_' for c in raw_name]
            base_name = "".join(clean_chars).strip('_')
            if not base_name:
                base_name = f"estrategia_{simbolo_slug}_{tf}"

        # 2. Persistir copia certificada en promovidas/
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archivo_strat = PROMOVIDAS_DIR / f"{base_name}_{ts_str}.py"

        # Blindaje de CONFIG_IA si el árbitro la referencia pero no está definida
        code_ia_final = (req.code_ia or "").strip()
        if "arbitro_ia(" in code_ia_final and "CONFIG_IA" in code_ia_final and "CONFIG_IA = {" not in code_ia_final:
            fallback_config = (
                "# -*- coding: utf-8 -*-\n"
                "CONFIG_IA = {\n"
                '    "asimetria_rr_minima": 2.0,\n'
                '    "rvol_4h": 1.15,\n'
                '    "rvol_1d": 1.25,\n'
                '    "rvol_minimo": 1.15,\n'
                '    "max_mecha_4h": 32.0,\n'
                '    "max_mecha_1d": 38.0,\n'
                '    "max_mecha_contra_pct": 32.0,\n'
                '    "max_dist_ema50_4h": 3.2,\n'
                '    "max_dist_ema50_1d": 4.2,\n'
                '    "max_distancia_ema50_atrs": 3.2,\n'
                "}\n\n"
            )
            code_ia_final = fallback_config + code_ia_final

        contenido = (
            f"# -*- coding: utf-8 -*-\n"
            f'"""\n'
            f'ESTRATEGIA CERTIFICADA EN BACKTEST LAB Y PROMOVIDA A PRODUCCIÓN\n'
            f'Activo: {simbolo} | Dataset: {ticker_ds} | Slot Asignado: {slot_id}\n'
            f'Fecha de Promoción: {datetime.now(timezone.utc).isoformat()}\n'
            f'"""\n\n'
            f"{req.code_math}\n\n"
            f"# --- ÁRBITRO HEURÍSTICO IA ---\n"
            f"{code_ia_final or '# Sin árbitro IA adicional'}\n"
        )
        archivo_strat.write_text(contenido, encoding="utf-8")

        # 2.1 Registrar en la carpeta física de destino seleccionada (SSOT)
        dest_cat = (req.destino or "principal").strip().lower()
        if dest_cat in ("principal", "panel_principal"):
            target_dir = BASE_DIR.parent / "backend" / "estrategias" / "catalogo" / "principal"
            cat_label = "Panel Principal (Cerebro Kula)"
        elif dest_cat in ("operador", "operador_presente"):
            target_dir = BASE_DIR.parent / "backend" / "estrategias" / "catalogo" / "operador_presente"
            cat_label = "Con Operador Presente"
        else:
            target_dir = BASE_DIR.parent / "backend" / "estrategias" / "catalogo" / "para_testear" / "ganadoras"
            cat_label = "Para Testear (Ganadoras)"

        # Resolución de colisión: nunca sobreescribir silenciosamente estrategias distintas
        cand_nombre = f"{base_name}.py"
        cand_path = target_dir / cand_nombre
        if cand_path.exists():
            existing_content = cand_path.read_text(encoding="utf-8")
            if existing_content.strip() != contenido.strip():
                if f"slot{slot_id}" not in base_name:
                    slot_cand = f"{base_name}_slot{slot_id}.py"
                    if not (target_dir / slot_cand).exists():
                        guardar_nombre = slot_cand
                    else:
                        c_idx = 2
                        while (target_dir / f"{base_name}_slot{slot_id}_{c_idx}.py").exists():
                            c_idx += 1
                        guardar_nombre = f"{base_name}_slot{slot_id}_{c_idx}.py"
                else:
                    c_idx = 2
                    while (target_dir / f"{base_name}_{c_idx}.py").exists():
                        c_idx += 1
                    guardar_nombre = f"{base_name}_{c_idx}.py"
            else:
                guardar_nombre = cand_nombre
        else:
            guardar_nombre = cand_nombre

        try:
            if target_dir.exists():
                dest_f = target_dir / guardar_nombre
                dest_f.write_text(contenido, encoding="utf-8")
                meta_path = target_dir / "metadata.json"
                meta_data = {}
                if meta_path.exists():
                    try:
                        meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                
                nombre_mostrado = req.nombre.strip() if (req.nombre and req.nombre.strip() not in generic_names) else dest_f.stem.replace('_', ' ').title()
                meta_data[dest_f.name] = {
                    "id": dest_f.stem,
                    "titulo": f"🚀 {nombre_mostrado} ({simbolo})",
                    "subtitulo": f"{cat_label} · Slot {slot_id} · Confianza {confianza}%",
                    "descripcion": req.justificacion.strip() if req.justificacion else f"Validada en Lab y promovida a {cat_label}.",
                    "dataset_sugerido": ticker_ds,
                    "timeframe": tf,
                    "lote_sugerido": 0.10 if dest_cat in ("principal", "panel_principal") else 0.01,
                    "activo_default": simbolo,
                    "rendimiento_lab": f"Promovida ({cat_label})"
                }
                meta_path.write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")

                # Espejar automáticamente en backtest_lab/estrategias_math/ para disponibilidad instantánea en selMath
                try:
                    math_dir = BASE_DIR / "estrategias_math"
                    if math_dir.exists():
                        (math_dir / dest_f.name).write_text(req.code_math, encoding="utf-8")
                        m_meta_file = math_dir / "metadata.json"
                        m_meta = {}
                        if m_meta_file.exists():
                            try:
                                m_meta = json.loads(m_meta_file.read_text(encoding="utf-8"))
                            except Exception:
                                pass
                        m_meta[dest_f.name] = f"🏆 [PROMOVIDA] {dest_f.stem} ({simbolo}) Slot {slot_id}"
                        m_meta_file.write_text(json.dumps(m_meta, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception as e_mirror:
                    logger.warning(f"No se pudo espejar en estrategias_math: {e_mirror}")

        except Exception as e_gan:
            logger.warning(f"No se pudo guardar en catalogo/{dest_cat}: {e_gan}")

        # 3. Inyectar Tarjeta de Oportunidad en el Buzón Radar (buzon_radar.json)
        card_id = f"lab-promoted-{uuid.uuid4().hex[:8]}"
        iso_now = datetime.now(timezone.utc).isoformat()
        
        justificacion = req.justificacion.strip() if req.justificacion else (
            f"Estrategia '{req.nombre}' validada en Backtest Lab con asimetría R:R garantizada, "
            f"asignada para auto-enrutamiento al Slot {slot_id} de Kula Balam."
        )

        try:
            from backend.radar_inbox import RadarInbox, OpportunityCard
            inbox = RadarInbox()
            card = OpportunityCard(
                id=card_id,
                timestamp=iso_now,
                activo=simbolo,
                titular=f"[LAB PROMOTION] {req.nombre} ({simbolo}) -> Slot {slot_id} [v:{card_id[-6:]}]",
                impacto="POSITIVO",
                confianza=confianza,
                justificacion=justificacion
            )
            inbox.add_cards([card])
        except Exception:
            # Si corre en standalone, escribir directamente a buzon_radar.json en PROJECT_ROOT
            buzon_path = BASE_DIR.parent / "buzon_radar.json"
            cards = []
            if buzon_path.exists():
                try:
                    cards = json.loads(buzon_path.read_text(encoding="utf-8"))
                except Exception:
                    cards = []
            cards.append({
                "id": card_id,
                "timestamp": iso_now,
                "activo": simbolo,
                "titular": f"[LAB PROMOTION] {req.nombre} ({simbolo}) -> Slot {slot_id} [v:{card_id[-6:]}]",
                "impacto": "POSITIVO",
                "confianza": confianza,
                "justificacion": justificacion
            })
            buzon_path.write_text(json.dumps(cards, indent=4, ensure_ascii=False), encoding="utf-8")

        # 4. Notificación opcional en caliente al puente Kula Balam si está escuchando
        daemon_notificado = False
        try:
            import urllib.request
            payload = json.dumps({
                "asset": simbolo,
                "text": justificacion,
                "confidence": confianza,
                "type": "OPORTUNIDAD",
                "source": "BACKTEST_LAB_PROMOTION",
                "timestamp": iso_now,
                "id": card_id
            }).encode("utf-8")
            req_http = urllib.request.Request(
                "http://127.0.0.1:18767/api/macro/inject",
                data=payload,
                headers={"Content-Type": "application/json", "X-API-Token": "kula_balam_default_token"}
            )
            with urllib.request.urlopen(req_http, timeout=1.0) as resp:
                if resp.status == 200:
                    daemon_notificado = True
        except Exception:
            pass

        return {
            "status": "ok",
            "mensaje": f"Estrategia '{req.nombre}' promovida con éxito al Slot {slot_id}.",
            "activo": simbolo,
            "dataset_base": ticker_ds,
            "slot_id": slot_id,
            "confianza": confianza,
            "card_id": card_id,
            "timestamp": iso_now,
            "archivo_guardado": str(archivo_strat.name),
            "daemon_en_vivo_notificado": daemon_notificado
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla al promover estrategia a producción: {str(e)}")

# ---------------------------------------------------------
# 5. BOTÓN ACTUALIZAR VELAS AL DÍA (INCREMENTAL Y NO DESTRUCTIVO)
# ---------------------------------------------------------
@app.post("/api/datasets/actualizar")
def actualizar_velas():
    reporte = []
    
    # 1. Actualizar TradFi y Forex vía Yahoo Finance (Incremental y No Destructivo)
    try:
        import yfinance as yf
        import pandas as pd
        tradfi_and_forex = [
            # Acciones e Índices TradFi (1d)
            ("SPY", "SPY", "1d", "2y"),
            ("QQQ", "QQQ", "1d", "2y"),
            ("AAPL", "AAPL", "1d", "2y"),
            ("MSFT", "MSFT", "1d", "2y"),
            ("NVDA", "NVDA", "1d", "2y"),
            ("AMD", "AMD", "1d", "2y"),
            ("GOOGL", "GOOGL", "1d", "2y"),
            ("AMZN", "AMZN", "1d", "2y"),
            ("META", "META", "1d", "2y"),
            ("TSLA", "TSLA", "1d", "2y"),
            # Forex Spot del Manual Black (1d y 1h)
            ("EURUSD=X", "EURUSD", "1d", "2y"),
            ("EURUSD=X", "EURUSD", "1h", "60d"),
            ("GBPUSD=X", "GBPUSD", "1d", "2y"),
            ("GBPUSD=X", "GBPUSD", "1h", "60d"),
            ("USDJPY=X", "USDJPY", "1d", "2y"),
            ("USDCAD=X", "USDCAD", "1d", "2y"),
        ]
        for yf_ticker, clean_symbol, tf, per in tradfi_and_forex:
            try:
                df_new = yf.download(yf_ticker, period=per, interval=tf, progress=False)
                if not df_new.empty:
                    if isinstance(df_new.columns, pd.MultiIndex):
                        df_new.columns = [c[0].lower() for c in df_new.columns]
                    else:
                        df_new.columns = [c.lower() for c in df_new.columns]
                    out_path = DATA_DIR / f"yf_{clean_symbol}_{tf}.parquet"
                    
                    if out_path.exists():
                        try:
                            df_prev = pd.read_parquet(out_path)
                            df_final = pd.concat([df_prev, df_new])
                            df_final = df_final[~df_final.index.duplicated(keep="last")].sort_index()
                        except Exception:
                            df_final = df_new.sort_index()
                    else:
                        df_final = df_new.sort_index()
                        
                    df_final.to_parquet(out_path)
                    last_date_str = df_final.index[-1].strftime('%Y-%m-%d %H:%M') if tf != "1d" else df_final.index[-1].strftime('%Y-%m-%d')
                    reporte.append(f"✓ {clean_symbol} ({tf}): {len(df_final)} velas al {last_date_str}")
            except Exception as ex:
                reporte.append(f"✗ Error en {clean_symbol} ({tf}): {str(ex)}")
    except Exception as ex:
        reporte.append(f"Error cargando yfinance: {str(ex)}")

    # 2. Actualizar Cripto vía Binance (ccxt) - Fusión Incremental No Destructiva
    try:
        import ccxt
        import pandas as pd
        ex = ccxt.binance({"enableRateLimit": True})
        crypto = [
            ("BTC/USDT", "5m", "binance_BTC_USDT_5m.parquet"),
            ("BTC/USDT", "15m", "binance_BTC_USDT_15m.parquet"),
            ("BTC/USDT", "1h", "binance_BTC_USDT_1h.parquet"),
            ("BTC/USDT", "4h", "binance_BTC_USDT_4h.parquet"),
            ("BTC/USDT", "1d", "binance_BTC_USDT_1d.parquet"),
            ("ETH/USDT", "5m", "binance_ETH_USDT_5m.parquet"),
            ("ETH/USDT", "15m", "binance_ETH_USDT_15m.parquet"),
            ("ETH/USDT", "1h", "binance_ETH_USDT_1h.parquet"),
            ("ETH/USDT", "4h", "binance_ETH_USDT_4h.parquet"),
            ("ETH/USDT", "1d", "binance_ETH_USDT_1d.parquet"),
            ("SOL/USDT", "5m", "binance_SOL_USDT_5m.parquet"),
            ("SOL/USDT", "1h", "binance_SOL_USDT_1h.parquet"),
            ("SOL/USDT", "4h", "binance_SOL_USDT_4h.parquet"),
            ("SOL/USDT", "1d", "binance_SOL_USDT_1d.parquet"),
        ]
        for pair, tf, fname in crypto:
            try:
                out_path = DATA_DIR / fname
                df_prev = None
                since_ts = None
                if out_path.exists():
                    try:
                        df_prev = pd.read_parquet(out_path)
                        if not df_prev.empty and isinstance(df_prev.index, pd.DatetimeIndex):
                            # Iniciar desde la última vela registrada menos 1 vela de margen
                            since_ts = int(df_prev.index[-1].timestamp() * 1000) - 60000
                    except Exception:
                        df_prev = None

                params = {"limit": 1000}
                if since_ts:
                    ohlcv = ex.fetch_ohlcv(pair, timeframe=tf, since=since_ts, limit=1000)
                else:
                    ohlcv = ex.fetch_ohlcv(pair, timeframe=tf, limit=1000)

                if ohlcv:
                    df_new = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df_new["timestamp"] = pd.to_datetime(df_new["timestamp"], unit="ms")
                    df_new.set_index("timestamp", inplace=True)
                    
                    if df_prev is not None and not df_prev.empty:
                        df_final = pd.concat([df_prev, df_new])
                        df_final = df_final[~df_final.index.duplicated(keep="last")].sort_index()
                    else:
                        df_final = df_new.sort_index()
                        
                    df_final.to_parquet(out_path)
                    reporte.append(f"✓ {pair} ({tf}): {len(df_final)} velas consolidadas al {df_final.index[-1].strftime('%Y-%m-%d %H:%M')}")
                else:
                    reporte.append(f"• {pair} ({tf}): Sin nuevas velas")
            except Exception as ex:
                reporte.append(f"✗ Error en {pair}: {str(ex)}")
    except Exception as ex:
        reporte.append(f"(Cripto omitido o sin conexión: {str(ex)})")

    texto_log = "\n".join(reporte)
    return {"status": "ok", "log": texto_log}

# Servir frontend con encabezados anti-caché estrictos
WEB_DIR = BASE_DIR / "web"

@app.get("/", response_class=HTMLResponse)
def get_index():
    index_path = WEB_DIR / "index.html"
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    response = HTMLResponse(content=content)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
