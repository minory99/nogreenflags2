from dataclasses import dataclass


@dataclass
class CompatResult:
    score: float
    coverage_a: float
    coverage_b: float
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
    coverage_a, a_covered = _coverage(a_flaws, b_tolerance)
    coverage_b, b_covered = _coverage(b_flaws, a_tolerance)

    score = (coverage_a + coverage_b) / 2
    return CompatResult(
        score=round(score, 3),
        coverage_a=round(coverage_a, 3),
        coverage_b=round(coverage_b, 3),
        a_flaws_covered=a_covered,
        b_flaws_covered=b_covered,
    )
