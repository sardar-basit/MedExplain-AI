"""Upload a fixture with abnormal values and audit explanation language."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
FIXTURE = Path("fixtures/lab_lipid.png")

SUSPECT = [
    r"this means you have",
    r"you are diagnosed",
    r"\byou have (diabetes|anemia|cancer|infection|disease)\b",
    r"\bprescrib",
    r"\bdosage\b",
    r"\btake\s+\d",
    r"\btreat(ment)? with\b",
]


def multipart_upload(path: Path) -> dict:
    boundary = "----MedExplainExplain"
    data = path.read_bytes()
    body = b"\r\n".join(
        [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"'.encode(),
            b"Content-Type: image/png",
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


def main() -> None:
    up = multipart_upload(FIXTURE)
    report_id = up["report_id"]
    with urllib.request.urlopen(f"{API}/api/v1/reports/{report_id}", timeout=60) as resp:
        detail = json.loads(resp.read().decode())

    print("report_id:", report_id)
    print("report_type:", detail.get("report_type"))
    print("\n=== overall_summary ===")
    print(detail.get("ai_summary"))
    print("\n=== per_result_explanations ===")
    print(json.dumps(detail.get("result_explanations"), indent=2))
    print("\n=== doctor_questions ===")
    print(json.dumps(detail.get("doctor_questions"), indent=2))
    print("\n=== test_results (status) ===")
    for row in detail.get("test_results") or []:
        print(f"  {row['marker_name']}: {row['value']} {row['unit']} -> {row['status']}")

    texts = [detail.get("ai_summary") or ""]
    texts.extend(detail.get("doctor_questions") or [])
    for item in detail.get("result_explanations") or []:
        texts.append(item.get("explanation") or "")
    blob = "\n".join(texts)
    print("\n=== language audit ===")
    flags = []
    for pattern in SUSPECT:
        if re.search(pattern, blob, flags=re.IGNORECASE):
            flags.append(pattern)
    if flags:
        print("FLAGGED patterns:", flags)
    else:
        print("No hard diagnostic/treatment patterns flagged.")
    if "consult a licensed healthcare professional" not in (detail.get("ai_summary") or "").lower():
        print("FLAGGED: missing disclaimer in overall_summary")
    else:
        print("Disclaimer present in overall_summary.")


if __name__ == "__main__":
    main()
