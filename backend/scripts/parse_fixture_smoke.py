"""Upload Phase-4 fixtures and print OCR text vs structured test_results."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8000"
FIXTURES = [
    Path("fixtures/lab_cbc.png"),
    Path("fixtures/lab_cmp.png"),
    Path("fixtures/lab_lipid.png"),
]


def multipart_upload(path: Path) -> dict:
    boundary = "----MedExplainBoundaryParse"
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


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    for path in FIXTURES:
        print("=" * 78)
        print(f"SOURCE IMAGE: {path.name}")
        try:
            up = multipart_upload(path)
            report_id = up["report_id"]
            raw = get_json(f"{API}/api/v1/reports/{report_id}/raw-text")
            detail = get_json(f"{API}/api/v1/reports/{report_id}")
            print(f"report_id: {report_id}")
            print(f"report_type: {detail.get('report_type')}")
            print("\n--- OCR raw_text ---")
            print(raw.get("raw_text") or "(empty)")
            print("\n--- structured test_results (JSON) ---")
            rows = detail.get("test_results") or []
            print(json.dumps(rows, indent=2))
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read().decode(errors='replace')}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
