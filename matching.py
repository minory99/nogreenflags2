"""
Логика подсчёта совместимости двух людей по принципу
"взаимодополняемость + толерантность к недостаткам".

score(A, B) = средняя из:
  coverage_A = доля недостатков A, которые Б готов терпеть
  coverage_B = доля недостатков Б, которые A готов терпеть

Если у человека вообще не указано недостатков, его coverage считается 1.0
(терпеть нечего, не наказываем пустой профиль).
"""

from dataclasses import dataclass


@dataclass
class CompatResult:
    score: float          # 0.0 - 1.0
    coverage_a: float     # насколько B терпит недостатки A
    coverage_b: float     # насколько A терпит недостатки B
    a_flaws_covered: set
    b_flaws_covered: set


def _coverage(flaws: list[str], tolerance_of_other: list[str]) -> tuple[float, set]:
    if not flaws:
        return 1.0, set()
    flaws_set = set(flaws)
    tol_set = set(tolerance_of_other)
    covered = flaws_set & tol_set
    return len(covered) / len(flaws_set), covered


def compute_compatibility(
    a_flaws: list[str],
    a_tolerance: list[str],
    b_flaws: list[str],
    b_tolerance: list[str],
) -> CompatResult:
    coverage_a, a_covered = _coverage(a_flaws, b_tolerance)   # Б терпит недостатки А
    coverage_b, b_covered = _coverage(b_flaws, a_tolerance)   # А терпит недостатки Б

    score = (coverage_a + coverage_b) / 2
    return CompatResult(
        score=round(score, 3),
        coverage_a=round(coverage_a, 3),
        coverage_b=round(coverage_b, 3),
        a_flaws_covered=a_covered,
        b_flaws_covered=b_covered,
    )
