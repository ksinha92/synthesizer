"""Statistical synthetic engine — GaussianCopula + CTGAN, built from scratch using copulas/ctgan libraries."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import cloudpickle
import numpy as np
import pandas as pd
import structlog

from app.domain.synthetic.entities import SyntheticConfig
from app.domain.synthetic.services import BaseSyntheticEngine
from app.infrastructure.engine.faker_engine import _build_generation_order

logger = structlog.get_logger()

_STAT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="statistical")

MAX_TRAINING_ROWS = 50_000
DEFAULT_CTGAN_TIMEOUT = 300  # 5 minutes
DEFAULT_CTGAN_EPOCHS = 300
DEFAULT_CTGAN_BATCH = 500


class StatisticalEngine(BaseSyntheticEngine):
    """Distribution-preserving synthesis via GaussianCopula or CTGAN."""

    def __init__(self, method: str = "gaussian_copula", config: dict | None = None) -> None:
        self._method = method
        self._config = config or {}
        self._storage = None  # Set externally for model persistence

    def set_storage(self, storage) -> None:
        self._storage = storage

    async def generate(
        self, config: SyntheticConfig, schema_metadata: dict
    ) -> dict[str, list[dict]]:
        tables_config = config.tables or []
        relationships = schema_metadata.get("relationships", [])
        order, cycles = _build_generation_order(tables_config, relationships)

        generated: dict[str, list[dict]] = {}
        source_data = schema_metadata.get("source_data", {})

        for table_name in order:
            table_cfg = next((t for t in tables_config if t.get("table_name") == table_name), None)
            if not table_cfg:
                continue

            row_count = table_cfg.get("row_count", config.row_count)
            real_df = source_data.get(table_name)

            if real_df is None or (isinstance(real_df, pd.DataFrame) and real_df.empty):
                logger.warning("statistical_no_source", table=table_name)
                continue

            if not isinstance(real_df, pd.DataFrame):
                real_df = pd.DataFrame(real_df)

            # Sample for training if too large
            if len(real_df) > MAX_TRAINING_ROWS:
                logger.info("statistical_sampling", table=table_name, original=len(real_df), sampled=MAX_TRAINING_ROWS)
                real_df = real_df.sample(n=MAX_TRAINING_ROWS, random_state=42)

            # Check for cached model
            model = await self._load_model(config.id, table_name)

            if model is None or self._config.get("retrain", False):
                if self._method == "ctgan":
                    model = await self._fit_ctgan(real_df, table_name)
                else:
                    model = await self._fit_copula(real_df, table_name)

                await self._save_model(config.id, table_name, model)

            # Sample
            if self._method == "ctgan":
                synthetic_df = await self._sample_ctgan(model, row_count)
            else:
                synthetic_df = await self._sample_copula(model, row_count)

            generated[table_name] = synthetic_df.to_dict(orient="records")

        logger.info(
            "statistical_generation_complete",
            method=self._method,
            tables=len(generated),
            total_rows=sum(len(r) for r in generated.values()),
        )
        return generated

    async def preview(
        self, config: SyntheticConfig, schema_metadata: dict, limit: int = 10
    ) -> dict[str, list[dict]]:
        preview_config = SyntheticConfig(
            **{k: v for k, v in config.__dict__.items() if k != "_events"},
            _events=[],
        )
        preview_config.row_count = limit
        for t in (preview_config.tables or []):
            t["row_count"] = limit

        # For preview, use reduced CTGAN epochs
        original_config = self._config.copy()
        if self._method == "ctgan":
            self._config["epochs"] = min(self._config.get("epochs", 50), 50)

        result = await self.generate(preview_config, schema_metadata)
        self._config = original_config
        return result

    # --- GaussianCopula ---

    async def _fit_copula(self, data: pd.DataFrame, table_name: str):
        def _fit():
            from copulas.multivariate import GaussianMultivariate

            # Prepare: select numeric + encode categorical
            numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
            cat_cols = data.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

            fit_data = data[numeric_cols + cat_cols].copy()

            # Encode categoricals as ordinal for copula fitting
            encoders = {}
            for col in cat_cols:
                fit_data[col] = fit_data[col].astype(str)
                categories = fit_data[col].unique()
                mapping = {v: i for i, v in enumerate(categories)}
                encoders[col] = {i: v for v, i in mapping.items()}
                fit_data[col] = fit_data[col].map(mapping).astype(float)

            fit_data = fit_data.dropna()

            model = GaussianMultivariate()
            model.fit(fit_data)

            return {"model": model, "encoders": encoders, "numeric_cols": numeric_cols, "cat_cols": cat_cols}

        loop = asyncio.get_event_loop()
        start = time.monotonic()
        result = await loop.run_in_executor(_STAT_EXECUTOR, _fit)
        logger.info("copula_fitted", table=table_name, duration_ms=round((time.monotonic() - start) * 1000))
        return result

    async def _sample_copula(self, model_data: dict, num_rows: int) -> pd.DataFrame:
        def _sample():
            model = model_data["model"]
            encoders = model_data["encoders"]
            cat_cols = model_data["cat_cols"]

            sampled = model.sample(num_rows)

            # Decode categoricals back
            for col in cat_cols:
                if col in sampled.columns:
                    sampled[col] = sampled[col].round().astype(int).map(encoders.get(col, {})).fillna("unknown")

            return sampled

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_STAT_EXECUTOR, _sample)

    # --- CTGAN ---

    async def _fit_ctgan(self, data: pd.DataFrame, table_name: str):
        epochs = self._config.get("epochs", DEFAULT_CTGAN_EPOCHS)
        batch_size = self._config.get("batch_size", DEFAULT_CTGAN_BATCH)
        timeout = self._config.get("timeout", DEFAULT_CTGAN_TIMEOUT)

        def _fit():
            from ctgan import CTGANSynthesizer

            discrete_cols = data.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
            synthesizer = CTGANSynthesizer(
                epochs=epochs,
                batch_size=batch_size,
                verbose=False,
            )
            synthesizer.fit(data, discrete_columns=discrete_cols)
            return synthesizer

        loop = asyncio.get_event_loop()
        start = time.monotonic()

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(_STAT_EXECUTOR, _fit),
                timeout=timeout,
            )
            logger.info("ctgan_fitted", table=table_name, epochs=epochs, duration_ms=round((time.monotonic() - start) * 1000))
            return result
        except asyncio.TimeoutError:
            logger.warning("ctgan_timeout", table=table_name, timeout=timeout)
            raise TimeoutError(f"CTGAN training exceeded {timeout}s timeout for table {table_name}")

    async def _sample_ctgan(self, model, num_rows: int) -> pd.DataFrame:
        def _sample():
            return model.sample(num_rows)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_STAT_EXECUTOR, _sample)

    # --- Model Persistence ---

    async def _save_model(self, config_id, table_name: str, model) -> None:
        if self._storage is None:
            return
        try:
            data = cloudpickle.dumps(model)
            path = f"models/{config_id}/{table_name}.pkl"
            await self._storage.save(path, data)
            logger.info("model_saved", config_id=str(config_id), table=table_name, size_bytes=len(data))
        except Exception as e:
            logger.warning("model_save_failed", error=str(e))

    async def _load_model(self, config_id, table_name: str):
        if self._storage is None:
            return None
        try:
            path = f"models/{config_id}/{table_name}.pkl"
            data = await self._storage.load(path)
            return cloudpickle.loads(data)
        except (FileNotFoundError, Exception):
            return None
