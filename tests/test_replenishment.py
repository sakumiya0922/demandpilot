import math

import pytest

from demandpilot.replenishment import recommended_replenishment


@pytest.mark.parametrize("demand,current,safety,expected", [(100.2, 50, 10, 61), (100, 50, 10, 60),
                                                          (100, 110, 10, 0), (100, 1000, 10, 0), (0, 0, 0, 0)])
def test_replenishment_formula(demand, current, safety, expected):
    assert recommended_replenishment(demand, current, safety) == expected


@pytest.mark.parametrize("values", [(-1, 0, 0), (1, -1, 0), (1, 0, -1), (math.nan, 0, 0),
                                     (math.inf, 0, 0), (1, 1.5, 0)])
def test_invalid_stock_inputs(values):
    with pytest.raises(ValueError):
        recommended_replenishment(*values)
