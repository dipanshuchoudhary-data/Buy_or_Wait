from __future__ import annotations

from decimal import Decimal
from typing import Any


def amounts_close(left: Any, right: Any, rel: Decimal = Decimal("0.02"), abs_tol: Decimal = Decimal("1")) -> bool:
    try:
        a = Decimal(str(left))
        b = Decimal(str(right))
    except Exception:
        return False
    if a == b:
        return True
    diff = abs(a - b)
    scale = max(abs(b), Decimal("1"))
    return diff <= abs_tol or diff / scale <= rel
