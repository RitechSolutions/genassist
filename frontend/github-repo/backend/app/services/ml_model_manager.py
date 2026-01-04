"""
ML Model Manager - Singleton pattern for efficient ML model caching

This module provides a singleton manager that loads and caches ML models,
avoiding repeated file I/O and deserialization overhead.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import pickle
import os
from typing import Dict, Optional, Any
from datetime import datetime
from uuid import UUID

from injector import inject

logger = logging.getLogger(__name__)

# Shared thread pool for blocking I/O operations (pickle loading)
# Using ThreadPoolExecutor with pre-validation to prevent problematic models
# Models are validated in a subprocess before being loaded to detect segfaults
_MODEL_LOAD_EXECUTOR = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="ml_model_loader"
)


def _load_pickle_sync(pkl_file: str) -> Any:
    """
    Synchronous function to load pickle file.
    This will be executed in a thread pool to avoid blocking the event loop.
    """
    # Try multiple loading methods
    load_errors = []

    # Method 1: Try pickle with default encoding (works best for XGBoost in thread pool)
    try:
        with open(pkl_file, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Loaded model using pickle (default) from {pkl_file}")
        return model
    except Exception as e:
        load_errors.append(f"pickle (default) failed: {str(e)}")

    # Method 2: Try pickle with latin1 encoding
    try:
        with open(pkl_file, 'rb') as f:
            model = pickle.load(f, encoding='latin1')
        logger.info(f"Loaded model using pickle (latin1) from {pkl_file}")
        return model
    except Exception as e:
        load_errors.append(f"pickle (latin1) failed: {str(e)}")

    # Method 3: Try joblib (may have threading issues with XGBoost)
    try:
        import joblib  # type: ignore
        model = joblib.load(pkl_file)
        logger.info(f"Loaded model using joblib from {pkl_file}")
        return model
    except ImportError:
        load_errors.append("joblib not available")
    except Exception as e:
        load_errors.append(f"joblib failed: {str(e)}")

    # If all methods failed, raise error
    error_details = "; ".join(load_errors)
    raise Exception(
        f"Could not load model file. Tried multiple methods: {error_details}. "
        f"Ensure the model was saved with pickle/joblib and all dependencies are installed."
    )


class CachedMLModel:
    """Container for a cached ML model with metadata"""

    def __init__(self, model: Any, model_id: UUID, updated_at: datetime, pkl_file: str):
        self.model = model
        self.model_id = model_id
        self.updated_at = updated_at
        self.pkl_file = pkl_file
        self.load_time = datetime.now()

    def is_stale(self, current_updated_at: datetime) -> bool:
        """Check if the cached model is stale (model has been updated)"""
        return self.updated_at < current_updated_at


@inject
class MLModelManager:
    """
    Singleton manager for ML model instances.

    This manager:
    1. Loads and caches model instances by model_id
    2. Tracks model update timestamps to detect changes
    3. Reloads only when a model has been updated
    4. Handles multiple loading methods (joblib, pickle)
    """

    _instance: Optional['MLModelManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> 'MLModelManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'MLModelManager':
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize the manager"""
        if not hasattr(self, '_cached_models'):
            self._cached_models: Dict[str, CachedMLModel] = {}
            self._loading_locks: Dict[str, asyncio.Lock] = {}
            logger.info("MLModelManager initialized")

    async def get_model(
        self,
        model_id: UUID,
        pkl_file: str,
        updated_at: datetime
    ) -> Any:
        """
        Get a cached model or load it if not cached/stale.

        Args:
            model_id: UUID of the ML model
            pkl_file: Path to the pickle file
            updated_at: Last update timestamp from database

        Returns:
            Loaded model object
        """
        model_id_str = str(model_id)

        # Check if model is cached and not stale
        if model_id_str in self._cached_models:
            cached = self._cached_models[model_id_str]
            if not cached.is_stale(updated_at):
                logger.debug(f"Using cached model {model_id_str}")
                return cached.model
            else:
                logger.info(f"Model {model_id_str} is stale, reloading...")

        # Ensure we have a lock for this model
        if model_id_str not in self._loading_locks:
            async with self._lock:
                if model_id_str not in self._loading_locks:
                    self._loading_locks[model_id_str] = asyncio.Lock()

        # Use lock to prevent concurrent loading of the same model
        async with self._loading_locks[model_id_str]:
            # Double-check pattern - model might have been loaded while waiting
            if model_id_str in self._cached_models:
                cached = self._cached_models[model_id_str]
                if not cached.is_stale(updated_at):
                    return cached.model

            # Load the model
            logger.info(f"Loading ML model {model_id_str} from {pkl_file}")
            model = await self._load_model_from_file(pkl_file)

            # Cache the model
            self._cached_models[model_id_str] = CachedMLModel(
                model=model,
                model_id=model_id,
                updated_at=updated_at,
                pkl_file=pkl_file
            )

            logger.info(f"Cached ML model {model_id_str}")
            return model

    async def _validate_model_safe(self, pkl_file: str) -> None:
        """
        Pre-validate model file in a subprocess to detect segfaults before loading.

        This runs the validation in an isolated subprocess, so if the model causes
        a segfault, it only crashes the subprocess, not the main application.

        Args:
            pkl_file: Path to the pickle file

        Raises:
            Exception: If validation fails
        """
        from app.core.utils.model_validator import validate_pickle_file_safe

        # Run validation in subprocess (non-blocking)
        loop = asyncio.get_running_loop()
        is_valid, error = await loop.run_in_executor(
            None,  # Use default executor for this quick check
            validate_pickle_file_safe,
            pkl_file,
            5  # 5 second timeout for validation
        )

        if not is_valid:
            logger.error(f"Model validation failed: {pkl_file} - {error}")
            raise ValueError(
                f"Model validation failed: {error}. "
                f"Please re-save the model with current library versions."
            )

        logger.debug(f"Model validation passed: {pkl_file}")

    async def _load_model_from_file(self, pkl_file: str) -> Any:
        """
        Load a model from a pickle file asynchronously with validation and timeout protection.

        This method:
        1. Pre-validates the model in a subprocess (detects segfaults safely)
        2. Loads the model in a thread pool (non-blocking)
        3. Applies timeout to prevent indefinite hangs

        Args:
            pkl_file: Path to the pickle file

        Returns:
            Loaded model object

        Raises:
            FileNotFoundError: If file not found
            ValueError: If model validation fails
            TimeoutError: If loading takes longer than timeout
            Exception: If loading fails
        """
        if not os.path.exists(pkl_file):
            raise FileNotFoundError(f"Model file not found: {pkl_file}")

        # Step 1: Validate model in subprocess (prevents segfaults from crashing main app)
        logger.debug(f"Pre-validating model file: {pkl_file}")
        await self._validate_model_safe(pkl_file)

        # Step 2: Load model in thread pool with timeout
        loop = asyncio.get_running_loop()
        logger.debug(f"Offloading pickle load to thread pool for {pkl_file}")

        try:
            # Set a timeout of 60 seconds for model loading
            # Large models should load within this time; if not, something is wrong
            model = await asyncio.wait_for(
                loop.run_in_executor(
                    _MODEL_LOAD_EXECUTOR,
                    _load_pickle_sync,
                    pkl_file
                ),
                timeout=60.0  # 60 second timeout
            )
            return model
        except asyncio.TimeoutError:
            logger.error(f"Model loading timed out after 60s: {pkl_file}")
            raise TimeoutError(
                f"Model loading timed out after 60 seconds. "
                f"The model file may be corrupted or incompatible: {pkl_file}"
            )

    def invalidate_model(self, model_id: UUID) -> None:
        """
        Invalidate (remove) a model from cache.

        Args:
            model_id: UUID of the model to invalidate
        """
        model_id_str = str(model_id)
        if model_id_str in self._cached_models:
            del self._cached_models[model_id_str]
            logger.info(f"Invalidated cached model {model_id_str}")

    def clear_cache(self) -> None:
        """Clear all cached models"""
        count = len(self._cached_models)
        self._cached_models.clear()
        logger.info(f"Cleared {count} cached models")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache and thread pool"""
        # Get thread pool stats
        executor_stats = {
            "executor_type": "ThreadPoolExecutor (with subprocess pre-validation)",
            "max_workers": _MODEL_LOAD_EXECUTOR._max_workers,
            "thread_name_prefix": _MODEL_LOAD_EXECUTOR._thread_name_prefix,
            "active_threads": len(_MODEL_LOAD_EXECUTOR._threads) if hasattr(_MODEL_LOAD_EXECUTOR, '_threads') else 0,
            "pending_tasks": _MODEL_LOAD_EXECUTOR._work_queue.qsize() if hasattr(_MODEL_LOAD_EXECUTOR, '_work_queue') else 0,
        }

        return {
            "cached_models_count": len(self._cached_models),
            "cached_model_ids": list(self._cached_models.keys()),
            "cache_details": [
                {
                    "model_id": str(cached.model_id),
                    "pkl_file": cached.pkl_file,
                    "updated_at": cached.updated_at.isoformat(),
                    "load_time": cached.load_time.isoformat(),
                    "model_type": type(cached.model).__name__
                }
                for cached in self._cached_models.values()
            ],
            "thread_pool": executor_stats
        }


# Global instance getter for easy access
def get_ml_model_manager() -> MLModelManager:
    """Get the global ML Model Manager instance"""
    return MLModelManager.get_instance()
