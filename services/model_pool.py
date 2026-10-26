# ============================================================
# Model Pool — Multi-Model Rotation for 24/7 Operation
# ============================================================
# PURPOSE:
#   Maintains a pool of NVIDIA NIM models and rotates between
#   them when rate limits (429) are hit. This effectively
#   multiplies available API throughput by N models.
#
# HOW IT WORKS:
#   1. Defines a priority-ordered list of NVIDIA NIM models
#   2. Tracks each model's health status and cooldown timers
#   3. When a model returns 429, it's "cooled down" for 60s
#   4. The next healthy model in the pool is used instead
#   5. Models automatically recover after cooldown expires
#
# USAGE:
#   from services.model_pool import get_model_pool
#   pool = get_model_pool()
#   model_name = pool.get_best_model()    # Returns healthiest model
#   pool.report_rate_limit(model_name)     # Mark as rate-limited
#   pool.report_success(model_name)        # Mark as healthy
# ============================================================

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelStatus:
    """Tracks the health and usage of a single model."""
    name: str
    priority: int              # Lower = higher priority (1 = primary)
    is_healthy: bool = True
    cooldown_until: float = 0.0  # Unix timestamp when cooldown expires
    total_calls: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0

    @property
    def is_available(self) -> bool:
        """Check if this model is currently usable."""
        if not self.is_healthy:
            # Check if cooldown has expired
            if time.time() >= self.cooldown_until:
                self.is_healthy = True
                self.consecutive_failures = 0
                return True
            return False
        return True


# ============================================================
# DEFAULT MODEL POOL — NVIDIA NIM Free Tier Models
# ============================================================
# These are all available for free with an NVIDIA NIM API key.
# Ordered by quality/reliability for job matching tasks.
# ============================================================

DEFAULT_MODELS = [
    {"name": "openai/gpt-oss-20b", "priority": 1},
    {"name": "deepseek-ai/deepseek-v4.1-flash", "priority": 2},
    {"name": "mistralai/mistral-large-2-instruct", "priority": 3},
    {"name": "meta/llama-3.2-11b-vision-instruct", "priority": 4},
]


class ModelPool:
    """
    Manages a pool of LLM models with automatic rotation on rate limits.
    
    When a model returns HTTP 429 (rate limited), it's put into a cooldown
    period and the next available model is used instead. This allows the
    agent to run 24/7 without being blocked by any single model's rate limit.
    
    Example:
        pool = ModelPool()
        
        # Get the best available model
        model = pool.get_best_model()  # "meta/llama-3.1-70b-instruct"
        
        # If it gets rate-limited
        pool.report_rate_limit(model)
        
        # Next call automatically uses the next model
        model = pool.get_best_model()  # "meta/llama-3.3-70b-instruct"
    """

    def __init__(self, models: list[dict] = None, cooldown_seconds: int = 90):
        """
        Initialize the model pool.
        
        Args:
            models: List of dicts with 'name' and 'priority' keys.
                    If None, uses the default NVIDIA NIM models.
            cooldown_seconds: How long to wait before retrying a rate-limited model.
        """
        self.cooldown_seconds = cooldown_seconds
        model_list = models or DEFAULT_MODELS
        
        self.models: dict[str, ModelStatus] = {}
        for m in model_list:
            status = ModelStatus(name=m["name"], priority=m["priority"])
            self.models[m["name"]] = status

        print(f"[ModelPool] Initialized with {len(self.models)} models:")
        for m in sorted(self.models.values(), key=lambda x: x.priority):
            print(f"  #{m.priority}: {m.name}")

    def get_best_model(self) -> str:
        """
        Return the highest-priority model that is currently available.
        
        If all models are in cooldown, returns the one whose cooldown
        expires soonest (with a short wait).
        
        Returns:
            Model name string for the NVIDIA NIM API.
        """
        # Sort by priority, filter to available
        available = [
            m for m in sorted(self.models.values(), key=lambda x: x.priority)
            if m.is_available
        ]

        if available:
            chosen = available[0]
            return chosen.name

        # All models in cooldown — find the one that recovers soonest
        recovering = sorted(self.models.values(), key=lambda x: x.cooldown_until)
        soonest = recovering[0]
        wait_time = max(0, soonest.cooldown_until - time.time())
        
        if wait_time > 0:
            print(f"[ModelPool] All models in cooldown. Waiting {wait_time:.0f}s for {soonest.name}...")
            time.sleep(wait_time + 1)

        soonest.is_healthy = True
        soonest.consecutive_failures = 0
        return soonest.name

    def report_rate_limit(self, model_name: str):
        """
        Mark a model as rate-limited. It will be put into cooldown.
        
        Args:
            model_name: The model that returned 429.
        """
        if model_name in self.models:
            model = self.models[model_name]
            model.is_healthy = False
            model.consecutive_failures += 1
            model.total_failures += 1
            
            # Exponential cooldown: 90s, 180s, 360s (capped at 10 minutes)
            cooldown = min(
                self.cooldown_seconds * (2 ** (model.consecutive_failures - 1)),
                600
            )
            model.cooldown_until = time.time() + cooldown
            
            next_model = self.get_best_model()
            print(f"[ModelPool] {model_name} rate-limited. Cooling down {cooldown:.0f}s. Switching to {next_model}")

    def report_success(self, model_name: str):
        """
        Mark a successful API call. Resets consecutive failure counter.
        
        Args:
            model_name: The model that succeeded.
        """
        if model_name in self.models:
            model = self.models[model_name]
            model.total_calls += 1
            model.consecutive_failures = 0

    def get_stats(self) -> dict:
        """Return usage statistics for all models."""
        return {
            name: {
                "priority": m.priority,
                "total_calls": m.total_calls,
                "total_failures": m.total_failures,
                "is_available": m.is_available,
            }
            for name, m in sorted(self.models.items(), key=lambda x: x[1].priority)
        }


# ============================================================
# SINGLETON — One pool shared across the entire application
# ============================================================
_pool_instance: Optional[ModelPool] = None


def get_model_pool() -> ModelPool:
    """Get or create the global model pool instance."""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = ModelPool()
    return _pool_instance
