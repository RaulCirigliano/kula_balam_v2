"""
Módulo: data_loader.py
Proyecto: Kula Balam / Backtest Lab
Objetivo: Selector universal de activos, mercados y temporalidades fractales.
"""

from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd


class DataLoaderLab:
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).resolve().parent.parent / "data" / "datos_historicos"

    def cargar(
        self,
        activo: str,
        mercado: str = "stocks",
        timeframe_base: str = "5m",
        fractales: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        if fractales is None:
            fractales = ["1h", "1d", "1w"]

        patrones = [
            f"yf_{activo}_{timeframe_base}.parquet",
            f"{activo}_{timeframe_base}.parquet",
            f"{activo}.parquet",
            f"{mercado}_{activo}_{timeframe_base}.parquet",
        ]

        archivo_encontrado = None
        for p in patrones:
            ruta = self.base_dir / p
            if ruta.exists():
                archivo_encontrado = ruta
                break

        if not archivo_encontrado:
            coincidencias = list(self.base_dir.glob(f"*{activo}*.parquet"))
            if coincidencias:
                archivo_encontrado = coincidencias[0]
            else:
                raise FileNotFoundError(
                    f"No se encontró archivo para {activo} en {self.base_dir}."
                )

        print(f"[*] Cargando {activo} ({mercado}) desde: {archivo_encontrado.name}")
        df = pd.read_parquet(archivo_encontrado)
        df.columns = [str(c).lower() for c in df.columns]

        if not isinstance(df.index, pd.DatetimeIndex):
            col_t = next(
                (c for c in ["timestamp", "date", "datetime", "time", "open_time"] if c in df.columns),
                None,
            )
            if col_t:
                df[col_t] = pd.to_datetime(df[col_t])
                df = df.set_index(col_t)
            else:
                raise ValueError("No se detectó columna temporal válida en el dataset.")

        df = df.sort_index()

        mapeo_resample = {
            "15m": "15min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
            "1w": "W",
            "1m": "ME",
        }

        for tf in fractales:
            tf_norm = tf.lower()
            rule = mapeo_resample.get(tf_norm, tf)
            df_resampled = (
                df.resample(rule)
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )

            span_ema = 50 if len(df_resampled) >= 50 else max(10, len(df_resampled) // 2)
            df_resampled[f"ema_{tf_norm}"] = df_resampled["close"].ewm(span=span_ema, adjust=False).mean()
            df_resampled[f"sesgo_{tf_norm}"] = np.where(
                df_resampled["close"] > df_resampled[f"ema_{tf_norm}"], 1, -1
            )

            if tf_norm == "1h":
                df_resampled["swing_high_24h"] = (
                    df_resampled["high"].rolling(window=24, min_periods=5).max()
                )
                df_resampled["swing_low_24h"] = (
                    df_resampled["low"].rolling(window=24, min_periods=5).min()
                )
                rango = df_resampled["swing_high_24h"] - df_resampled["swing_low_24h"]
                df_resampled["pos_fibo_1h"] = (df_resampled["close"] - df_resampled["swing_low_24h"]) / (
                    rango + 1e-9
                )
                df[f"pos_fibo_{tf_norm}"] = (
                    df_resampled["pos_fibo_1h"].shift(1).reindex(df.index, method="ffill").bfill()
                )

            df[f"sesgo_{tf_norm}"] = (
                df_resampled[f"sesgo_{tf_norm}"].shift(1).reindex(df.index, method="ffill").bfill()
            )

        print(
            f"[*] Datos listos: {len(df)} velas base ({timeframe_base}) con marcos añadidos: {fractales}"
        )
        return df

    def particionar_is_oos(
        self, df: pd.DataFrame, ratio_is: float = 0.70
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Particiona el dataset en:
        - In-Sample (IS, optimización y entrenamiento).
        - Out-of-Sample (OOS, auditoría ciega fuera de muestra).
        """
        corte = int(len(df) * ratio_is)
        df_is = df.iloc[:corte].copy()
        df_oos = df.iloc[corte:].copy()
        print(f"[*] Partición IS/OOS (Ratio {ratio_is*100:.0f}%): {len(df_is)} velas IS | {len(df_oos)} velas OOS")
        return df_is, df_oos


if __name__ == "__main__":
    loader = DataLoaderLab()
    df = loader.cargar(activo="NVDA", mercado="stocks", timeframe_base="5m", fractales=["1h", "1d", "1w"])
    print(df[["close", "sesgo_1d", "sesgo_1w", "pos_fibo_1h"]].tail())
