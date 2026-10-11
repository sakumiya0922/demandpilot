"""Simple stock simulation, without lead times or order constraints."""

import math


def recommended_replenishment(predicted_quantity: float, current_stock: int, safety_stock: int) -> int:
    if any(not math.isfinite(value) or value < 0 for value in [predicted_quantity, current_stock, safety_stock]):
        raise ValueError("Forecast and stocks must be finite and nonnegative")
    if int(current_stock) != current_stock or int(safety_stock) != safety_stock:
        raise ValueError("Stock inputs must be whole units")
    return max(0, math.ceil(predicted_quantity + safety_stock - current_stock))
