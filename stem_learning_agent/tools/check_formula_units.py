"""check_formula_units: lightweight unit-consistency checker.

Pure rule-based. No LLM, no network, no API key.

Checks applied:
1. Same symbol with conflicting units across formulas → medium finding.
2. Missing or vacuous units ("?", "", "unknown", "n/a") → low/medium finding.
3. Known-symbol sanity rules (frequency→Hz, resistance→Ω, capacitance→F,
   time-constant→s) → medium finding on clear mismatch.

All findings use the existing `ReviewFinding` schema so the Reviewer and
Packager surfaces them without any new plumbing.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ..core.schemas import Formula, ReviewFinding


# ---------------------------------------------------------------------------
# Known-symbol sanity rules
# ---------------------------------------------------------------------------

# Each entry: (canonical normalised unit, aliases, expected symbol name hint)
# All unit sets use LOWER-CASE NORMALISED forms (via _normalise_unit).
_FREQ_UNITS = {"hz", "rad/s", "rad s", "rads", "hertz", "1/s", "s^-1", "s-1"}
_RESISTANCE_UNITS = {"ohm", "ohms"}
_CAPACITANCE_UNITS = {"f", "farad", "farads", "uf", "nf", "pf"}
_TIME_UNITS = {"s", "sec", "second", "seconds"}


def _normalise_unit(raw: str) -> str:
    """Normalize a unit string for comparison. Handles Unicode variation."""
    norm = raw.strip()
    # Map common Unicode variants to ASCII for comparison.
    mapping = {
        "Ω": "ohm",  # Greek capital Omega → ohm
        "Ω": "ohm",  # Ohm sign
        "μ": "u",    # Greek mu → u (for μF)
        "⁻": "-",    # superscript minus
    }
    for uni, ascii in mapping.items():
        norm = norm.replace(uni, ascii)
    return norm.lower()

# Known-symbol patterns — map a variable substring to expected unit families.
_KNOWN_SYMBOL_RULES: list[tuple[str, str, set[str], str]] = [
    # (symbol pattern, human label, expected units set, suggested unit)
    ("f_c", "cutoff frequency", _FREQ_UNITS, "Hz"),
    ("fc", "frequency", _FREQ_UNITS, "Hz"),
    ("omega", "angular frequency", _FREQ_UNITS, "rad/s"),
    ("ω", "angular frequency", _FREQ_UNITS, "rad/s"),
    ("freq", "frequency", _FREQ_UNITS, "Hz"),
    ("r", "resistance", _RESISTANCE_UNITS, "Ω"),  # only when standalone or capital R
    ("tau", "time constant", _TIME_UNITS, "s"),
    ("τ", "time constant", _TIME_UNITS, "s"),
    ("c", "capacitance", _CAPACITANCE_UNITS, "F"),
]


def _match_known_symbol(var_name: str) -> Optional[tuple[str, str, set[str], str]]:
    """Return the best known-symbol rule match for a variable name, or None."""
    vl = var_name.strip().lower()
    if not vl:
        return None
    # Exact match first, then substring.
    for pattern, label, units, suggestion in _KNOWN_SYMBOL_RULES:
        if vl == pattern:
            return (pattern, label, units, suggestion)
    for pattern, label, units, suggestion in _KNOWN_SYMBOL_RULES:
        # Substring match: only if the pattern is a meaningful sub-word.
        if vl == "r" and pattern == "r":
            return (pattern, label, units, suggestion)
        if len(pattern) > 1 and pattern in vl:
            return (pattern, label, units, suggestion)
    return None


# ---------------------------------------------------------------------------
# Checker functions
# ---------------------------------------------------------------------------


def _check_1_same_symbol_conflicting_units(
    formulas: list[Formula],
) -> list[ReviewFinding]:
    """Per-symbol: if the same variable appears with different units, flag it."""
    # Build: symbol → list of (unit_str, formula_id)
    symbol_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for f in formulas:
        for var, unit in f.units.items():
            norm = _normalise_unit(unit)
            if norm in ("", "?", "unknown", "n/a"):
                continue  # handled by check_2
            symbol_map[var].append((unit, f.id))

    findings: list[ReviewFinding] = []
    for var, entries in symbol_map.items():
        unique_units: set[str] = set()
        for unit_str, _fid in entries:
            unique_units.add(_normalise_unit(unit_str))
        if len(unique_units) <= 1:
            continue
        formula_ids = sorted({e[1] for e in entries})
        unit_list = ", ".join(e[0] for e in entries)
        findings.append(
            ReviewFinding(
                severity="medium",
                category="formula",
                message=(
                    f"Variable '{var}' has conflicting units across formulas: {unit_list}"
                ),
                evidence=(
                    f"Formula ids: {', '.join(formula_ids)}. "
                    f"Unique normalised units: {', '.join(sorted(unique_units))}"
                ),
                suggested_fix=(
                    f"Manually review which unit is correct for '{var}' "
                    "and update the affected formulas."
                ),
            )
        )
    return findings


def _check_2_missing_or_vacuous_units(
    formulas: list[Formula],
) -> list[ReviewFinding]:
    """Flag formulas where variables have missing or placeholder units."""
    findings: list[ReviewFinding] = []
    unknown_vars_by_formula: dict[str, list[str]] = defaultdict(list)
    unknown_vars_global: set[str] = set()

    for f in formulas:
        for var in f.variables:
            unit = f.units.get(var, "").strip().lower()
            if unit in ("", "?", "unknown", "n/a") or not unit:
                unknown_vars_by_formula[f.id].append(var)
                unknown_vars_global.add(var)

    for fid, vars_list in sorted(unknown_vars_by_formula.items()):
        severity = "low" if len(vars_list) <= 1 else "medium"
        findings.append(
            ReviewFinding(
                severity=severity,  # type: ignore[arg-type]
                category="formula",
                message=(
                    f"Formula '{fid}' has variables with missing or placeholder units: "
                    f"{', '.join(vars_list)}"
                ),
                evidence=f"Variables with unknown/vacuous units: {', '.join(vars_list)}",
                suggested_fix="Manually determine and fill in the correct units.",
            )
        )

    if unknown_vars_global:
        findings.append(
            ReviewFinding(
                severity="medium",
                category="formula",
                message=(
                    f"Multiple formulas have unknown units across variables: "
                    f"{', '.join(sorted(unknown_vars_global))}"
                ),
                evidence=f"Variables with unknown units globally: {', '.join(sorted(unknown_vars_global))}",
                suggested_fix="Review and fill in units for these variables across all affected formulas.",
            )
        )

    return findings


def _check_3_known_symbol_mismatch(
    formulas: list[Formula],
) -> list[ReviewFinding]:
    """Check known symbols against expected unit families. Conservative: only
    flag when the mismatch is unambiguous (e.g. f_c in Ω, R in Hz, C in s)."""
    findings: list[ReviewFinding] = []
    for f in formulas:
        for var, unit_str in f.units.items():
            norm = _normalise_unit(unit_str)
            if norm in ("", "?", "unknown", "n/a"):
                continue
            rule = _match_known_symbol(var)
            if rule is None:
                continue
            pattern, label, expected_units, suggestion = rule
            if norm in expected_units:
                continue  # match — OK
            findings.append(
                ReviewFinding(
                    severity="medium",
                    category="formula",
                    message=(
                        f"Variable '{var}' ({label}) has unexpected unit '{unit_str}' "
                        f"in formula {f.id}"
                    ),
                    evidence=(
                        f"Expected a {label}-type unit like {', '.join(sorted(expected_units)[:4])}. "
                        f"Got: '{unit_str}'. Suggestion: '{suggestion}'."
                    ),
                    suggested_fix=(
                        f"Check if '{var}' in formula {f.id} is actually a {label} "
                        f"and update the unit to '{suggestion}' or similar."
                    ),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def check_formula_units(formulas: list[Formula]) -> list[ReviewFinding]:
    """Run all unit-consistency checks and return findings.

    These checks are conservative: they flag conflicts and obvious mismatches
    but never assert correctness. All findings carry **medium** or **low**
    severity and recommend human review.

    Args:
        formulas: List of Formula objects from parsed/formulas.json.

    Returns:
        List of ReviewFinding objects ready for merging into ReviewReport.
    """
    if not formulas:
        return [
            ReviewFinding(
                severity="low",
                category="formula",
                message="No formulas available for unit-consistency check.",
                suggested_fix="Run the formula extraction step first.",
            )
        ]

    findings: list[ReviewFinding] = []
    findings.extend(_check_1_same_symbol_conflicting_units(formulas))
    findings.extend(_check_2_missing_or_vacuous_units(formulas))
    findings.extend(_check_3_known_symbol_mismatch(formulas))

    if not findings:
        findings.append(
            ReviewFinding(
                severity="low",
                category="formula",
                message="Unit-consistency check passed: no conflicts or obvious mismatches detected.",
            )
        )
    return findings
