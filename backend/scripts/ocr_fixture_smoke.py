"""Upload fixture images and print OCR raw_text."""

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
    boundary = "----MedExplainBoundary7MA4YWxkTrZu0gW"
    data = path.read_bytes()
    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"'.encode(),
        b"Content-Type: image/png",
        b"",
        data,
        f"--{boundary}--".encode(),
        b"",
    ]
    body = b"\r\n".join(parts)
    req = urllib.request.Request(
        f"{API}/api/v1/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    for path in FIXTURES:
        print("=" * 72)
        print(f"FILE: {path.name}")
        try:
            up = multipart_upload(path)
            print(f"report_id: {up['report_id']}")
            print(f"file_url:  {up['file_url']}")
            with urllib.request.urlopen(
                f"{API}/api/v1/reports/{up['report_id']}/raw-text",
                timeout=30,
            ) as resp:
                raw = json.loads(resp.read().decode())
            print("--- raw_text ---")
            print(raw.get("raw_text") or "(empty)")
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read().decode(errors='replace')}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
