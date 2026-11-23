"""Tiny module used by the sample unit tests."""


def add(a: float, b: float) -> float:
    # Intentional bug so the demo shows AI root-cause analysis.
    # Change `a - b` to `a + b` to make the suite green.
    return a - b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
