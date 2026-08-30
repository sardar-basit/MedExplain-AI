"""QA suite: upload lab PNG/PDF fixtures and print a pass/fail matrix."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
CASES = [
    ("lab_cbc.png", True, ["Hemoglobin", "Platelets"]),
    ("lab_cmp.png", True, ["Glucose", "Sodium"]),
    ("lab_lipid.png", True, ["Total Cholesterol", "HDL Cholesterol"]),
    ("lab_cbc.pdf", True, ["Hemoglobin", "WBC"]),
    # ALT is more OCR-stable on PDF than Creatinine (often dropped by Tesseract)
    ("lab_cmp.pdf", True, ["Glucose", "ALT"]),
    ("lab_lipid.pdf", True, ["LDL Cholesterol", "Triglycerides"]),
    # Negative control: tiny / empty image → parsing_failed (no invented rows)
    ("sample-report.png", False, []),
]


def upload(path: Path) -> dict:
    boundary = "----QABoundary"
    data = path.read_bytes()
    ctype = "application/pdf" if path.suffix.lower() == ".pdf" else "image/png"
    body = b"\r\n".join(
        [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"'.encode(),
            f"Content-Type: {ctype}".encode(),
            b"",
            data,
            f"--{boundary}--".encode(),
            b"",
        ]
    )
    req = urllib.request.Request(
        f"{API}/api/v1/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def get_report(report_id: str) -> dict:
    with urllib.request.urlopen(f"{API}/api/v1/reports/{report_id}", timeout=60) as resp:
        return json.loads(resp.read().decode())


def _has_marker(markers: list[str], expected: str) -> bool:
    needle = expected.lower()
    return any(needle in m.lower() or m.lower() in needle for m in markers)


def _status_of(status_map: dict[str, str], name: str) -> str | None:
    for key, value in status_map.items():
        if name.lower() in key.lower() or key.lower() in name.lower():
            return value
    return None


def main() -> None:
    root = Path("fixtures")
    rows = []
    for filename, expect_ok, must_include in CASES:
        path = root / filename
        print("=" * 72)
        print(f"CASE: {filename} (expect_ok={expect_ok})")
        try:
            up = upload(path)
            detail = get_report(up["report_id"])
            status = detail.get("report_type")
            markers = [r["marker_name"] for r in detail.get("test_results") or []]
            ok = (
                (expect_ok and status in {"parsed", "explained"} and len(markers) > 0)
                or ((not expect_ok) and status == "parsing_failed")
            )
            missing = [m for m in must_include if not _has_marker(markers, m)] if expect_ok else []
            if missing:
                ok = False

            status_map = {
                r["marker_name"]: r["status"] for r in detail.get("test_results") or []
            }
            notes: list[str] = []
            checks = [
                ("cbc", "Hemoglobin", "LOW"),
                ("cbc", "Platelets", "HIGH"),
                ("cmp", "Glucose", "HIGH"),
                ("lipid", "Total Cholesterol", "HIGH"),
            ]
            for kind, marker, want in checks:
                if kind not in filename:
                    continue
                got = _status_of(status_map, marker)
                if got is not None and got != want:
                    notes.append(f"{marker} should be {want}, got {got}")
                    ok = False

            result = {
                "file": filename,
                "pass": ok,
                "report_type": status,
                "report_id": up["report_id"],
                "markers": markers,
                "missing": missing,
                "notes": notes,
                "summary_present": bool(detail.get("ai_summary")),
                "questions": len(detail.get("doctor_questions") or []),
            }
            rows.append(result)
            print(json.dumps(result, indent=2))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            rows.append({"file": filename, "pass": False, "error": f"HTTP {exc.code}: {body}"})
            print("ERROR", body)
        except Exception as exc:  # noqa: BLE001
            rows.append({"file": filename, "pass": False, "error": str(exc)})
            print("ERROR", exc)

    passed = sum(1 for r in rows if r.get("pass"))
    print("\n" + "=" * 72)
    print(f"QA SUMMARY: {passed}/{len(rows)} passed")
    for r in rows:
        mark = "PASS" if r.get("pass") else "FAIL"
        print(f"  [{mark}] {r.get('file')} -> {r.get('report_type') or r.get('error')}")


if __name__ == "__main__":
    main()
