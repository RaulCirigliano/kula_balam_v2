# -*- coding: utf-8 -*-
"""
Módulo: backend/estrategias/catalogo_manager.py
Proyecto: Kula Balam & Backtest Lab
Propósito: Gestor Unificado del Catálogo de Fórmulas y Ciclo de Vida Cuantitativo.
Maneja las 3 carpetas físicas de estrategias:
  1. principal/ (Cerebro Kula Autónomo)
  2. operador_presente/ (Trading con Presencia / Scalping 5M)
  3. para_testear/ (ganadoras/ y heredadas/)

Permite:
  - Listar dinámicamente el catálogo completo en tiempo real.
  - Cargar código matemático puro y árbitro de IA para el sandbox de Lab.
  - Eliminar de raíz una estrategia de ambos lados (Lab y Kula Balam).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CATALOGO_DIR = BASE_DIR / "catalogo"
PRINCIPAL_DIR = CATALOGO_DIR / "principal"
OPERADOR_DIR = CATALOGO_DIR / "operador_presente"
TESTEAR_DIR = CATALOGO_DIR / "para_testear"
GANADORAS_DIR = TESTEAR_DIR / "ganadoras"
HEREDADAS_DIR = TESTEAR_DIR / "heredadas"

PROJECT_ROOT = BASE_DIR.parent.parent
CONFIG_FILE = PROJECT_ROOT / "data" / "strategies_config.json"


def _read_metadata(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error leyendo {meta_path}: {e}")
    return {}


def _write_metadata(folder: Path, data: Dict[str, Any]) -> None:
    meta_path = folder / "metadata.json"
    meta_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_catalogo_completo() -> Dict[str, Any]:
    """Retorna el árbol dinámico completo de fórmulas del sistema agrupadas en 3 categorías."""
    # 1. Panel Principal
    meta_p = _read_metadata(PRINCIPAL_DIR)
    principal_items = []
    if PRINCIPAL_DIR.exists():
        for f in sorted(PRINCIPAL_DIR.glob("*.py")):
            info = meta_p.get(f.name, {})
            principal_items.append({
                "archivo": f.name,
                "categoria": "principal",
                "id": info.get("id", f.stem),
                "titulo": info.get("titulo", f.stem),
                "subtitulo": info.get("subtitulo", info.get("descripcion", "")),
                "descripcion": info.get("descripcion", ""),
                "timeframe": info.get("timeframe", "4h"),
                "lote_sugerido": float(info.get("lote_sugerido", 0.10)),
                "dataset_sugerido": info.get("dataset_sugerido", "binance_SOL_USDT_4h.parquet"),
                "activo_default": info.get("activo_default", "SOL/USDT"),
                "rendimiento_lab": info.get("rendimiento_lab", "Lab Validado")
            })

    # 2. Con Operador Presente (Scalping 5M / 15M)
    meta_op = _read_metadata(OPERADOR_DIR)
    operador_items = []
    if OPERADOR_DIR.exists():
        for f in sorted(OPERADOR_DIR.glob("*.py")):
            info = meta_op.get(f.name, {})
            operador_items.append({
                "archivo": f.name,
                "categoria": "operador_presente",
                "id": info.get("id", f.stem),
                "titulo": info.get("titulo", f.stem),
                "subtitulo": info.get("subtitulo", info.get("descripcion", "")),
                "descripcion": info.get("descripcion", ""),
                "timeframe": info.get("timeframe", "5m"),
                "lote_sugerido": float(info.get("lote_sugerido", 0.01)),
                "dataset_sugerido": info.get("dataset_sugerido", "binance_ETH_USDT_5m.parquet"),
                "activo_default": info.get("activo_default", "ETH/USDT"),
                "rendimiento_lab": info.get("rendimiento_lab", "Lab Validado")
            })

    # 3. Para Testear: Ganadoras y Heredadas
    meta_gan = _read_metadata(GANADORAS_DIR)
    ganadoras_items = []
    if GANADORAS_DIR.exists():
        for f in sorted(GANADORAS_DIR.glob("*.py")):
            info = meta_gan.get(f.name, {})
            ganadoras_items.append({
                "archivo": f.name,
                "categoria": "para_testear_ganadoras",
                "id": info.get("id", f.stem),
                "titulo": info.get("titulo", f.stem),
                "subtitulo": info.get("subtitulo", info.get("descripcion", "")),
                "descripcion": info.get("descripcion", ""),
                "timeframe": info.get("timeframe", "4h"),
                "lote_sugerido": float(info.get("lote_sugerido", 0.01)),
                "dataset_sugerido": info.get("dataset_sugerido", "binance_BTC_USDT_4h.parquet"),
                "rendimiento_lab": info.get("rendimiento_lab", "Ganadora Lab")
            })

    meta_her = _read_metadata(HEREDADAS_DIR)
    heredadas_items = []
    if HEREDADAS_DIR.exists():
        for f in sorted(HEREDADAS_DIR.glob("*.py")):
            info = meta_her.get(f.name, {})
            heredadas_items.append({
                "archivo": f.name,
                "categoria": "para_testear_heredadas",
                "id": info.get("id", f.stem),
                "titulo": info.get("titulo", f.stem),
                "subtitulo": info.get("subtitulo", info.get("descripcion", "")),
                "descripcion": info.get("descripcion", ""),
                "timeframe": info.get("timeframe", "4h"),
                "lote_sugerido": float(info.get("lote_sugerido", 0.01)),
                "dataset_sugerido": info.get("dataset_sugerido", "binance_BTC_USDT_4h.parquet"),
                "rendimiento_lab": "Auditoría en Curso"
            })

    return {
        "panel_principal": principal_items,
        "operador_presente": operador_items,
        "para_testear": {
            "ganadoras": ganadoras_items,
            "heredadas": heredadas_items,
        }
    }


def _resolver_directorio(categoria: str) -> Optional[Path]:
    cat = categoria.strip().lower()
    if cat in ("principal", "panel_principal"):
        return PRINCIPAL_DIR
    elif cat in ("operador_presente", "operador"):
        return OPERADOR_DIR
    elif cat in ("ganadoras", "para_testear_ganadoras"):
        return GANADORAS_DIR
    elif cat in ("heredadas", "para_testear_heredadas"):
        return HEREDADAS_DIR
    return None


def get_formula_detalle(categoria: str, archivo: str) -> Optional[Dict[str, Any]]:
    """Carga una fórmula del catálogo y extrae code_math y code_ia para Lab."""
    folder = _resolver_directorio(categoria)
    if not folder:
        return None
    file_path = folder / archivo
    if not file_path.exists() or not file_path.is_file():
        return None

    raw_code = file_path.read_text(encoding="utf-8")
    meta = _read_metadata(folder).get(archivo, {})

    code_math = raw_code
    code_ia = ""
    if "# --- ÁRBITRO HEURÍSTICO IA ---" in raw_code:
        parts = raw_code.split("# --- ÁRBITRO HEURÍSTICO IA ---")
        code_math = parts[0].strip()
        code_ia = parts[1].strip()
    elif "def arbitro_ia(" in raw_code:
        parts = raw_code.split("def arbitro_ia(")
        code_math = parts[0].strip()
        code_ia = "# -*- coding: utf-8 -*-\n'''\nÁrbitro IA\n'''\ndef arbitro_ia(" + parts[1]

    return {
        "archivo": archivo,
        "categoria": categoria,
        "id": meta.get("id", file_path.stem),
        "titulo": meta.get("titulo", file_path.stem),
        "subtitulo": meta.get("subtitulo", meta.get("descripcion", "")),
        "descripcion": meta.get("descripcion", ""),
        "dataset_sugerido": meta.get("dataset_sugerido", "binance_BTC_USDT_4h.parquet"),
        "timeframe": meta.get("timeframe", "4h"),
        "lote_sugerido": float(meta.get("lote_sugerido", 0.01)),
        "code_math": code_math,
        "code_ia": code_ia,
    }


def eliminar_formula(categoria: str, archivo: str) -> Dict[str, Any]:
    """
    Elimina físicamente una fórmula de su carpeta en el catálogo, actualiza metadata.json
    y purga la estrategia de la configuración de Kula Balam.
    """
    folder = _resolver_directorio(categoria)
    if not folder:
        raise ValueError(f"Categoría inválida: {categoria}")

    file_path = folder / archivo
    if not file_path.exists():
        raise FileNotFoundError(f"El archivo {archivo} no existe en {categoria}")

    # 1. Leer id de la estrategia
    meta = _read_metadata(folder)
    info = meta.pop(archivo, {})
    strat_id = info.get("id", file_path.stem)

    # 2. Borrar archivo físico
    file_path.unlink()
    _write_metadata(folder, meta)

    # 3. Purgar de strategies_config.json en Kula Balam
    if CONFIG_FILE.exists():
        try:
            cfg_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if strat_id in cfg_data:
                del cfg_data[strat_id]
                CONFIG_FILE.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info(f"Estrategia {strat_id} eliminada de strategies_config.json")
        except Exception as e:
            logger.warning(f"Error actualizando strategies_config.json tras borrar {strat_id}: {e}")

    # 4. Desactivar en config_manager en memoria si está cargado
    try:
        from backend.estrategias.config_manager import StrategyConfigManager
        if strat_id in StrategyConfigManager._configs:
            del StrategyConfigManager._configs[strat_id]
        if strat_id in StrategyConfigManager.DEFAULT_STRATEGY_CONFIGS:
            del StrategyConfigManager.DEFAULT_STRATEGY_CONFIGS[strat_id]
    except Exception:
        pass

    logger.info(f"Fórmula '{archivo}' (ID: {strat_id}) eliminada con éxito de {categoria} y Kula Balam.")
    return {
        "status": "ok",
        "eliminado": archivo,
        "strat_id": strat_id,
        "categoria": categoria,
        "mensaje": f"Fórmula '{archivo}' eliminada físicamente de Lab y desautorizada en Kula Balam."
    }
