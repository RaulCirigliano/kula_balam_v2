"""
Estrategia Cuantitativa: Tres Velas, Wyckoff VPA y Benchmark Bulkowski.
Módulo desacoplado y portable para trading algorítmico multitemporal.
"""

try:
    from backend.estrategias.tres_velas_wyckoff_bulkowski import (
        EstrategiaTresVelas,
        TRES_VELAS_TIMEFRAMES,
    )
except ImportError:
    # Soporte standalone en caso de ejecutarse fuera de la raíz de kula_balam
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from backend.estrategias.tres_velas_wyckoff_bulkowski import (
        EstrategiaTresVelas,
        TRES_VELAS_TIMEFRAMES,
    )

__all__ = ["EstrategiaTresVelas", "TRES_VELAS_TIMEFRAMES"]
