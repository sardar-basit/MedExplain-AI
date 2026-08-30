"""Offline tabular OCR parser + template explanations for local/dev.

This is NOT a silent fake of Qwen. Parsing only extracts tabular OCR rows.
Explanations use fixed educational templates (no invented diagnoses).
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from app.core.errors import AppError
from app.models import ResultStatus
from app.schemas.llm_explain import ExplanationBundle, ResultExplanationItem
from app.schemas.llm_parse import ParsedTestResult
from app.services.llm.base import LLMService
from app.services.llm.explain_validate import DISCLAIMER

_ROW_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9\-\s/()%]{1,60}?)\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>[A-Za-z%μµ^/\d.*-]{0,20})?\s*"
    r"(?:"
    r"(?P<rmin>\d+(?:\.\d+)?)\s*[-–]\s*(?P<rmax>\d+(?:\.\d+)?)"
    r"|"
    r"[<>]\s*(?P<bound>\d+(?:\.\d+)?)"
    r")?\s*$"
)

# Require a lab-like unit and/or an explicit reference range to avoid
# matching intake-form OCR noise ("Problems Seok 2", "Diabetes 1 D").
_LAB_UNIT_RE = re.compile(
    r"^(?:"
    r"%|"
    r"g/?dL|"
    r"mg/?d[lLt]|"
    r"mmol/?L|"
    r"U/?L|"
    r"IU/?L|"
    r"fL|FL|"
    r"ng/?mL|"
    r"pg/?mL|"
    r"µg/?[dlLmL]|ug/?[dlLmL]|"
    r"10[\^*]?[36]/?[uµ]?/?[lL]|"
    r"10[\^*]?[36]/?/?uL|"
    r"x?10\^?[36]/?/?[uµ]?L|"
    r"cells?/?[uµ]?L|"
    r"mm/?hr|"
    r"mEq/?L"
    r")$",
    re.IGNORECASE,
)

_SKIP_PREFIXES = (
    "city lab",
    "metabolic",
    "lipid",
    "sample",
    "patient",
    "fixture",
    "name:",
    "date",
    "medical",
    "history",
    "allerg",
    "signature",
    "introduction",
    "referring",
    "contact",
    "laboratory investigation",
    "complete blood",
    "test result",
)

# Phone-camera GCC / Wafid forms rarely keep clean table rows. Match known
# markers even when OCR mangles spelling ("Haarogkbin", "Creatiriee").
_KNOWN_MARKERS: tuple[tuple[str, tuple[str, ...], str | None], ...] = (
    (
        "Hemoglobin",
        ("haemoglobin", "hemoglobin", "haarogkbin", "haanogbbn", "haemoglob"),
        "g/dL",
    ),
    ("RBS", ("r.b.s", "rbs", "random blood sugar"), "mg/dL"),
    (
        "Creatinine",
        (
            "creatinine",
            "creatinin",
            "creatinice",
            "creatirice",
            "creatirnee",
            "creatnize",
            "creatinize",
            "creatiriee",
            "crearice",
            "creatine",
        ),
        "mg/dL",
    ),
    ("BMI", ("bmi", "body mass index"), None),
    ("Height", ("height",), "cm"),
    ("Weight", ("weight",), "kg"),
    ("Pulse", ("pulse/min", "pulse", "pulolrin", "pukolrin", "pusattin", "pusatrin", "pusolrin"), "bpm"),
    ("Respiratory Rate", ("rr/min", "rr /min", "respiration"), "/min"),
)

# Unit may appear before or after the value: "Haemoglobin g/dL 13.6"
_FORM_ROW_RE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9.\-\s/%()]{1,40}?)"
    r"(?:\s+(?P<unit_before>g/?dL|mg/?d[lL]|mmol/?L|U/?L|cm|kg|%))?"
    r"\s*[:=]?\s*"
    r"(?P<value>\d+(?:\.\d+)?)"
    r"(?:\s*(?P<unit_after>g/?dL|mg/?d[lL]|mmol/?L|U/?L|cm|kg|%))?",
    re.IGNORECASE,
)


def _is_plausible_lab_row(
    *,
    name: str,
    unit: str | None,
    reference_min: float | None,
    reference_max: float | None,
) -> bool:
    cleaned_name = " ".join(name.split())
    if len(cleaned_name) < 3 or len(cleaned_name) > 40:
        return False
    # Reject names that are mostly non-letters (OCR garbage).
    letters = sum(ch.isalpha() for ch in cleaned_name)
    if letters < max(3, int(len(cleaned_name) * 0.55)):
        return False
    has_range = reference_min is not None or reference_max is not None
    has_unit = bool(unit and _LAB_UNIT_RE.match(unit.replace(" ", "")))
    return has_range or has_unit


def _fix_decimal_ocr(canonical: str, value: float) -> float:
    """Phone OCR often drops the decimal: Hb 13.6 → 136, RBS 96.0 → 960."""
    if canonical == "Hemoglobin" and 30.0 <= value <= 250.0:
        return round(value / 10.0, 2)
    if canonical == "RBS" and value >= 400.0:
        return round(value / 10.0, 2)
    if canonical == "Creatinine" and 2.0 <= value <= 20.0 and float(value).is_integer():
        return round(value / 10.0, 2)
    if canonical == "Pulse" and value > 200:
        last_two = int(value) % 100
        if 40 <= last_two <= 180:
            return float(last_two)
        if value >= 400:
            return round(value / 10.0, 2)
    return value


def _extract_known_markers(raw_text: str) -> list[ParsedTestResult]:
    """Pull numeric labs from messy camera OCR using known marker aliases."""
    lowered = raw_text.lower().replace("\n", " ")
    found: list[ParsedTestResult] = []
    seen: set[str] = set()

    for canonical, aliases, default_unit in _KNOWN_MARKERS:
        if canonical in seen:
            continue
        best: ParsedTestResult | None = None
        for alias in aliases:
            for match in re.finditer(re.escape(alias), lowered):
                window = lowered[match.start() : match.start() + 48]
                tail = window[len(alias) :]
                number = re.search(r"(\d+(?:\.\d+)?)", tail)
                if not number:
                    number = re.search(r"(\d+(?:\.\d+)?)", window)
                if not number:
                    continue
                value = _fix_decimal_ocr(canonical, float(number.group(1)))
                if canonical == "Hemoglobin" and not (4.0 <= value <= 22.0):
                    continue
                if canonical == "RBS" and not (40.0 <= value <= 600.0):
                    continue
                if canonical == "Creatinine" and not (0.1 <= value <= 15.0):
                    continue
                if canonical == "BMI" and not (10.0 <= value <= 60.0):
                    continue
                if canonical == "Height" and not (100.0 <= value <= 230.0):
                    continue
                if canonical == "Weight" and not (30.0 <= value <= 250.0):
                    continue
                if canonical == "Pulse" and not (40.0 <= value <= 200.0):
                    continue
                if canonical == "Respiratory Rate" and not (8.0 <= value <= 40.0):
                    continue
                best = ParsedTestResult(
                    test_name=canonical,
                    value=value,
                    unit=default_unit,
                    reference_min=None,
                    reference_max=None,
                    status=ResultStatus.NORMAL,
                )
                break
            if best:
                break
        if best:
            seen.add(canonical)
            found.append(best)
    return found


_QUALITATIVE_FINDINGS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("HIV I & II", ("hiv i", "hiv i&ii", "hiv1", "hiv 1", "hovibi", "hovibit"), ("negative", "positive")),
    ("HBsAg", ("hbs ag", "hbsag", "hosag", "hbs"), ("negative", "positive")),
    ("Anti-HCV", ("anti hcv", "anti-hcv", "hcv", "ahcv"), ("negative", "positive")),
    ("VDRL / TPHA", ("vdrl", "tpha", "tphag"), ("negative", "positive")),
    ("Malaria", ("malaria", "malana", "mslana"), ("absent", "present", "negative", "positive")),
    ("Microfilaria", ("micro filaria", "microfilaria", "mikrofilari", "kro flaris"), ("absent", "present", "negative", "positive")),
    ("Colour Vision", ("colour vision", "color vision", "colourvision", "cesourviern", "ceourvenn"), ("normal", "abnormal")),
    ("Chest X-Ray", ("chest x-ray", "chest x ray", "chex ray", "che ray"), ("nad", "normal", "abnormal")),
    ("LFT", ("l.f.t", "lft", "liver function"), ("normal", "abnormal")),
    ("Urine Sugar", ("urine sugar", "urine  sugar"), ("negative", "positive", "absent")),
    ("Urine Albumin", ("urine albumin", "albumin", "albumen"), ("negative", "positive", "absent")),
    ("Stool Parasites", ("helminthes", "helminths", "ova", "cyst"), ("absent", "present", "negative")),
)


def _normalize_finding_token(token: str) -> str:
    token = token.lower().strip(" .,:;")
    mapping = {
        "nad": "NAD",
        "normal": "Normal",
        "abnormal": "Abnormal",
        "negative": "Negative",
        "positive": "Positive",
        "absent": "Absent",
        "present": "Present",
        "neernat": "Normal",
        "neemnal": "Normal",
        "assert": "Absent",
        "aseet": "Absent",
        "abie": "Absent",
        "abrent": "Absent",
        "advent": "Absent",
        "negathes": "Negative",
        "negaties": "Negative",
        "negathre": "Negative",
        "negatlee": "Negative",
    }
    return mapping.get(token, token.title())


def _extract_qualitative_findings(raw_text: str) -> list[ParsedTestResult]:
    """Serology / form checkboxes: Negative, Absent, NAD, Normal, blood group, etc."""
    lowered = raw_text.lower().replace("\n", " ")
    found: list[ParsedTestResult] = []
    seen: set[str] = set()

    # Blood group (A/B/O/AB ±)
    if "Blood Group" not in seen:
        bg = re.search(
            r"(?:blood\s*group|stood\s*group|seod\s*group|steod\s*group|bloodgroup)"
            r"[=:\s]*([aboab]{1,2})\s*([\+\-])?",
            lowered,
            re.IGNORECASE,
        )
        if bg:
            group = (bg.group(1) + (bg.group(2) or "")).upper().replace(" ", "")
            # OCR often drops '+' — B alone is still useful; prefer B+ when Be/B e seen
            if group in {"A", "B", "O", "AB"}:
                nearby = lowered[bg.start() : bg.start() + 24]
                if "+" in nearby or " e" in nearby or nearby.endswith("e"):
                    group = f"{group}+"
            if group in {"A", "A+", "A-", "B", "B+", "B-", "O", "O+", "O-", "AB", "AB+", "AB-"}:
                found.append(
                    ParsedTestResult(
                        test_name="Blood Group",
                        value=None,
                        value_text=group,
                        unit=None,
                        status=ResultStatus.NORMAL,
                    )
                )
                seen.add("Blood Group")

    # Blood pressure 110/70 (OCR often glues as 11070)
    if "Blood Pressure" not in seen:
        bp = re.search(
            r"(?:blood\s*pressure|bocd\s*preisure|ocd\s*pressure|bod\s*posure|posure|\bbp\b)"
            r"[^\d]{0,16}(\d{2,3})\s*[/\\]\s*(\d{2,3})",
            lowered,
        )
        if not bp:
            bp = re.search(
                r"(?:blood\s*pressure|bocd\s*preisure|ocd\s*pressure|bod\s*posure|posure)"
                r"[^\d]{0,16}(1[0-7]\d)([4-9]\d)\b",
                lowered,
            )
        if not bp:
            bp = re.search(r"\b(1[0-7]\d)\s*[/\\]\s*([4-9]\d)\b", lowered)
        if bp:
            systolic, diastolic = int(bp.group(1)), int(bp.group(2))
            if 70 <= systolic <= 220 and 40 <= diastolic <= 140:
                found.append(
                    ParsedTestResult(
                        test_name="Blood Pressure",
                        value=None,
                        value_text=f"{systolic}/{diastolic}",
                        unit="mmHg",
                        status=ResultStatus.NORMAL,
                    )
                )
                seen.add("Blood Pressure")

    # BMI when label missing but classic xx.xx appears near height/weight block
    if "BMI" not in seen:
        bmi = re.search(r"\bbmi\b[^\d]{0,12}(\d{2}(?:\.\d{1,2})?)", lowered)
        if not bmi:
            bmi = re.search(r"\b(1[5-9]|2\d|3[0-9]|4[0-5])\.\d{2}\b", lowered)
        if bmi:
            value = float(bmi.group(1))
            if 12.0 <= value <= 50.0:
                found.append(
                    ParsedTestResult(
                        test_name="BMI",
                        value=value,
                        unit=None,
                        status=ResultStatus.NORMAL,
                    )
                )
                seen.add("BMI")

    # Visual acuity fractions near left/right eye
    for label, aliases in (
        ("Visual Acuity (Left)", ("left eye", "lefteye", "leltoye", "letteye", "ldtqeg")),
        ("Visual Acuity (Right)", ("right eye", "righteye", "rigreeye", "rigteye", "righew")),
    ):
        if label in seen:
            continue
        for alias in aliases:
            for match in re.finditer(re.escape(alias), lowered):
                window = lowered[match.start() : match.start() + 40]
                frac = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", window)
                if not frac:
                    continue
                a, b = int(frac.group(1)), int(frac.group(2))
                if a > 30 or b > 40:
                    continue
                found.append(
                    ParsedTestResult(
                        test_name=label,
                        value=None,
                        value_text=f"{a}/{b}",
                        unit=None,
                        status=ResultStatus.NORMAL,
                    )
                )
                seen.add(label)
                break
            if label in seen:
                break

    for canonical, aliases, outcomes in _QUALITATIVE_FINDINGS:
        if canonical in seen:
            continue
        hit: ParsedTestResult | None = None
        for alias in aliases:
            for match in re.finditer(re.escape(alias), lowered):
                # Prefer tokens after the label; also allow short lookbehind.
                window = lowered[max(0, match.start() - 8) : match.start() + 56]
                for outcome in outcomes:
                    # OCR variants already normalized via word search
                    if re.search(rf"\b{re.escape(outcome)}\b", window):
                        text = _normalize_finding_token(outcome)
                        hit = ParsedTestResult(
                            test_name=canonical,
                            value=None,
                            value_text=text,
                            unit=None,
                            status=ResultStatus.NORMAL,
                        )
                        break
                # Fuzzy OCR endings near serology labels
                if hit is None:
                    fuzzy = re.search(
                        r"\b(negat\w*|absent|present|normal|nad|positive|assert|abrent)\b",
                        window[len(alias) :] if alias in window else window,
                    )
                    if fuzzy:
                        text = _normalize_finding_token(fuzzy.group(1))
                        if text in {
                            "Negative",
                            "Positive",
                            "Absent",
                            "Present",
                            "Normal",
                            "NAD",
                            "Abnormal",
                        }:
                            hit = ParsedTestResult(
                                test_name=canonical,
                                value=None,
                                value_text=text,
                                unit=None,
                                status=ResultStatus.NORMAL,
                            )
                if hit:
                    break
            if hit:
                break
        if hit:
            seen.add(canonical)
            found.append(hit)

    # One summary card when many systems are NAD (avoid 15 identical cards)
    nad_hits = len(re.findall(r"\bnad\b", lowered))
    if nad_hits >= 4 and "System Examination" not in seen:
        found.append(
            ParsedTestResult(
                test_name="System Examination",
                value=None,
                value_text="NAD (systems reviewed on report)",
                unit=None,
                status=ResultStatus.NORMAL,
            )
        )

    return found


def _range_phrase(rmin: float | None, rmax: float | None) -> str:
    if rmin is not None and rmax is not None:
        return f"{rmin}–{rmax}"
    if rmax is not None:
        return f"below {rmax}"
    if rmin is not None:
        return f"above {rmin}"
    return "the range listed on this report"


def _explain_one(row: dict[str, Any]) -> str:
    name = row["marker_name"]
    value_text = (row.get("value_text") or "").strip()
    unit = (row.get("unit") or "").strip()
    if value_text:
        value_txt = f"{value_text} {unit}".strip()
    else:
        value = row.get("value")
        value_txt = f"{value} {unit}".strip() if value is not None else "as listed"
    range_txt = _range_phrase(row.get("reference_min"), row.get("reference_max"))
    status = row.get("status")
    has_range = row.get("reference_min") is not None or row.get("reference_max") is not None

    if value_text and not has_range:
        return (
            f"Your report lists {name} as {value_txt}. This is copied from the form "
            f"for educational review only — it is not a diagnosis. Ask your doctor "
            f"if you have questions about what this finding means for you."
        )

    if status == ResultStatus.NORMAL.value or status == ResultStatus.NORMAL:
        return (
            f"Your {name} result was {value_txt}, which is within the usual range "
            f"shown on this report ({range_txt}). Being in range does not diagnose "
            f"any condition — your doctor can explain what this means for you."
        )
    if status == ResultStatus.HIGH.value or status == ResultStatus.HIGH:
        return (
            f"Your {name} was {value_txt}, which is higher than the range shown on "
            f"this report ({range_txt}). Higher readings can sometimes be linked to "
            f"conditions such as inflammation, diet patterns, or other medical factors "
            f"— your doctor can confirm the cause. This tool does not diagnose illness "
            f"or recommend treatment."
        )
    return (
        f"Your {name} was {value_txt}, which is lower than the range shown on this "
        f"report ({range_txt}). Lower readings can sometimes be linked to conditions "
        f"such as nutritional gaps, blood loss, or other medical factors — your doctor "
        f"can confirm the cause. This tool does not diagnose illness or recommend "
        f"treatment."
    )


def _dedupe_results(rows: list[ParsedTestResult]) -> list[ParsedTestResult]:
    by_key: dict[str, ParsedTestResult] = {}
    for row in rows:
        key = re.sub(r"[^a-z0-9]+", "", row.test_name.lower())
        # Prefer rows that already have a reference range.
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = row
            continue
        if existing.reference_min is None and existing.reference_max is None:
            if row.reference_min is not None or row.reference_max is not None:
                by_key[key] = row
    return list(by_key.values())


class OfflineLLMService(LLMService):
    async def parse_report(self, raw_text: str) -> list[ParsedTestResult]:
        if not raw_text or not raw_text.strip():
            raise AppError(
                code="empty_ocr_text",
                message="Cannot parse an empty OCR text.",
                status_code=400,
            )

        results: list[ParsedTestResult] = []
        for line in raw_text.splitlines():
            cleaned = " ".join(line.strip().split())
            if not cleaned:
                continue
            lower = cleaned.lower()
            if any(lower.startswith(prefix) for prefix in _SKIP_PREFIXES):
                continue
            match = _ROW_RE.match(cleaned)
            if not match:
                continue
            unit = (match.group("unit") or "").strip() or None
            rmin = match.group("rmin")
            rmax = match.group("rmax")
            bound = match.group("bound")
            reference_min = float(rmin) if rmin else None
            reference_max = float(rmax) if rmax else None
            if bound is not None and "<" in cleaned:
                reference_max = float(bound)
            if bound is not None and ">" in cleaned:
                reference_min = float(bound)
            name = match.group("name").strip()
            if not _is_plausible_lab_row(
                name=name,
                unit=unit,
                reference_min=reference_min,
                reference_max=reference_max,
            ):
                continue

            results.append(
                ParsedTestResult(
                    test_name=name,
                    value=float(match.group("value")),
                    unit=unit,
                    reference_min=reference_min,
                    reference_max=reference_max,
                    status=None,
                )
            )

        # Camera photos of GCC / Wafid candidate forms: recover labs via aliases.
        results.extend(_extract_known_markers(raw_text))
        results.extend(_extract_qualitative_findings(raw_text))
        results = _dedupe_results(results)

        if not results:
            raise AppError(
                code="llm_parse_failed",
                message=(
                    "No structured lab rows found in the OCR text. "
                    "Upload a clearer, closer photo of the lab section "
                    "(or a lab PDF), or set DASHSCOPE_API_KEY with "
                    "LLM_PROVIDER=dashscope for stronger parsing."
                ),
                status_code=422,
            )
        return results

    async def explain_results(
        self, test_results: list[dict[str, Any]]
    ) -> ExplanationBundle:
        if not test_results:
            raise AppError(
                code="explain_empty_input",
                message="No test results available to explain.",
                status_code=400,
            )

        explanations = [
            ResultExplanationItem(
                test_result_id=UUID(str(row["id"])),
                explanation=_explain_one(row),
            )
            for row in test_results
        ]

        flagged = [
            row
            for row in test_results
            if str(row.get("status")) in {ResultStatus.HIGH.value, ResultStatus.LOW.value}
        ]
        if flagged:
            names = ", ".join(row["marker_name"] for row in flagged)
            overall = (
                f"Most values on this report look within the listed ranges, but "
                f"{names} {'was' if len(flagged) == 1 else 'were'} outside the listed "
                f"range. An out-of-range result is not a diagnosis of any disease — your "
                f"clinician can review the full picture. {DISCLAIMER}"
            )
            questions = [
                f"What could explain my {row['marker_name']} result of "
                f"{(row.get('value_text') or row.get('value'))} "
                f"{(row.get('unit') or '').strip()}?".strip()
                for row in flagged[:3]
            ]
            while len(questions) < 3:
                questions.append(
                    f"Should we repeat {flagged[0]['marker_name']} or order related tests?"
                )
            if len(flagged) >= 1:
                questions.append(
                    "Are there lifestyle or follow-up steps you recommend while we "
                    f"look into {flagged[0]['marker_name']}?"
                )
            questions = questions[:5]
        else:
            sample = test_results[0]["marker_name"]
            overall = (
                f"All listed markers on this report, including {sample}, were within "
                f"the ranges shown. Staying in range does not diagnose health by itself. "
                f"{DISCLAIMER}"
            )
            questions = [
                f"Do my {sample} and other results need any follow-up?",
                f"How often should I recheck {sample}?",
                "Is there anything on this report you want to discuss further?",
            ]

        return ExplanationBundle(
            per_result_explanations=explanations,
            overall_summary=overall,
            doctor_questions=questions,
        )
