from .base import Strategy
from .sma_crossover import SMACrossover

REGISTRY = {cls.name: cls for cls in (SMACrossover,)}


def get_strategy(name: str, **params) -> Strategy:
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name](**params)
