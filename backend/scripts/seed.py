"""Database seeder script for Supabase storage and PostgreSQL tables."""

import os
import sys
import uuid
from pathlib import Path

# Add backend directory to sys.path and load environment variables
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

from supabase import Client, create_client


def get_supabase_admin_client() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    # Prefer service role key to bypass RLS during seeding; fallback to anon key or env var
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key or key == "[PASTE_SERVICE_ROLE_KEY_HERE]":
        key = os.getenv("SUPABASE_ANON_KEY", "").strip()

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY must be set in .env")

    return create_client(url, key)


def seed_database():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("🌱 Starting MedExplain AI Supabase Database & Storage Seeding...\n")
    client = get_supabase_admin_client()

    # 1. Storage Upload
    storage_filename = "sample_report.pdf"
    bucket_name = "medical-reports"
    dummy_bytes = (
        b"%PDF-1.4 Mock Blood Test Report content for MedExplain AI testing.\n"
        b"Hemoglobin: 14.2 g/dL, Fasting Glucose: 135.0 mg/dL, WBC: 6.5 10^3/uL, Vitamin D: 18.0 ng/mL."
    )

    file_public_url = f"{os.getenv('SUPABASE_URL', '').rstrip('/')}/storage/v1/object/public/{bucket_name}/{storage_filename}"
    try:
        client.storage.from_(bucket_name).upload(
            path=storage_filename,
            file=dummy_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        file_public_url = client.storage.from_(bucket_name).get_public_url(storage_filename)
        print(f"✅ Successfully uploaded '{storage_filename}' to storage bucket '{bucket_name}'.")
    except Exception as exc:
        print(f"⚠️ Storage upload notice: {exc}")

    # 2. Reports Table Seed
    report_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    raw_report_text = (
        "PATIENT LAB REPORT\n"
        "Patient Name: Jane Doe\n"
        "Date: 2026-08-30\n\n"
        "CBC & METABOLIC PANEL\n"
        "- Hemoglobin: 14.2 g/dL (Ref: 12.0 - 16.0)\n"
        "- Glucose: 135.0 mg/dL (Ref: 70.0 - 99.0)\n"
        "- White Blood Cells: 6.5 10^3/uL (Ref: 4.0 - 11.0)\n"
        "- Vitamin D: 18.0 ng/mL (Ref: 30.0 - 100.0)"
    )

    ai_summary_text = (
        "Comprehensive lab report interpretation: Blood count and white blood cell levels are normal. "
        "Fasting glucose is slightly elevated (135.0 mg/dL), and Vitamin D is below the recommended reference range (18.0 ng/mL). "
        "This summary is for educational purposes only."
    )

    report_row = {
        "id": report_id,
        "user_id": user_id,
        "file_url": file_public_url,
        "report_type": "explained",
        "raw_text": raw_report_text,
        "ai_summary": ai_summary_text,
    }

    try:
        res = client.table("reports").insert(report_row).execute()
        if res.data:
            report_id = res.data[0]["id"]
        print(f"✅ Successfully seeded report record into 'reports' table (Report ID: {report_id}).")
    except Exception as exc:
        print(f"❌ Failed to insert into 'reports' table: {exc}")
        return

    # 3. Test Results Table Seed (4 batch rows)
    test_results_batch = [
        {
            "id": str(uuid.uuid4()),
            "report_id": report_id,
            "biomarker": "Hemoglobin",
            "value": 14.2,
            "value_text": "14.2",
            "unit": "g/dL",
            "reference_min": 12.0,
            "reference_max": 16.0,
            "status": "NORMAL",
        },
        {
            "id": str(uuid.uuid4()),
            "report_id": report_id,
            "biomarker": "Glucose",
            "value": 135.0,
            "value_text": "135.0",
            "unit": "mg/dL",
            "reference_min": 70.0,
            "reference_max": 99.0,
            "status": "HIGH",
        },
        {
            "id": str(uuid.uuid4()),
            "report_id": report_id,
            "biomarker": "White Blood Cells",
            "value": 6.5,
            "value_text": "6.5",
            "unit": "10^3/uL",
            "reference_min": 4.0,
            "reference_max": 11.0,
            "status": "NORMAL",
        },
        {
            "id": str(uuid.uuid4()),
            "report_id": report_id,
            "biomarker": "Vitamin D",
            "value": 18.0,
            "value_text": "18.0",
            "unit": "ng/mL",
            "reference_min": 30.0,
            "reference_max": 100.0,
            "status": "LOW",
        },
    ]

    try:
        client.table("test_results").insert(test_results_batch).execute()
        print(f"✅ Successfully seeded {len(test_results_batch)} test results into 'test_results' table.")
    except Exception as exc:
        print(f"❌ Failed to insert into 'test_results' table: {exc}")

    # 4. Embeddings Table Seed (768-dimensional mock vector)
    mock_vector = [0.01] * 768
    embedding_row = {
        "id": str(uuid.uuid4()),
        "content": f"Mock RAG embedding context for report {report_id}",
        "metadata": {"report_id": report_id, "source": "seed.py"},
        "embedding": mock_vector,
    }

    try:
        client.table("embeddings").insert(embedding_row).execute()
        print("✅ Successfully seeded mock vector array into 'embeddings' table.")
    except Exception as exc:
        print(f"⚠️ Embeddings insert notice: {exc}")

    print("\n🎉 Database & Storage Seeding Complete!")


if __name__ == "__main__":
    seed_database()
