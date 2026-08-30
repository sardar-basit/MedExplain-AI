"""Seed the database with one fake user, report, and three test results."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models import Report, ResultStatus, TestResult, User

SEED_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SEED_REPORT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.id == SEED_USER_ID))
        if existing:
            print(f"Seed data already present (user_id={SEED_USER_ID}). Skipping.")
            return

        user = User(id=SEED_USER_ID)
        report = Report(
            id=SEED_REPORT_ID,
            user_id=SEED_USER_ID,
            file_url="local://seed/sample-cbc-report.pdf",
            report_type="CBC",
            ai_summary=(
                "This sample complete blood count shows mostly typical values, "
                "with hemoglobin slightly below the listed reference range. "
                "This is educational only — consult a licensed clinician."
            ),
        )
        results = [
            TestResult(
                report_id=SEED_REPORT_ID,
                marker_name="Hemoglobin",
                value=11.8,
                unit="g/dL",
                reference_min=12.0,
                reference_max=16.0,
                status=ResultStatus.LOW,
            ),
            TestResult(
                report_id=SEED_REPORT_ID,
                marker_name="White Blood Cell Count",
                value=7.2,
                unit="10^3/uL",
                reference_min=4.0,
                reference_max=11.0,
                status=ResultStatus.NORMAL,
            ),
            TestResult(
                report_id=SEED_REPORT_ID,
                marker_name="Platelets",
                value=420.0,
                unit="10^3/uL",
                reference_min=150.0,
                reference_max=400.0,
                status=ResultStatus.HIGH,
            ),
        ]

        session.add(user)
        session.add(report)
        session.add_all(results)
        await session.commit()

        print("Seeded:")
        print(f"  user.id          = {SEED_USER_ID}")
        print(f"  report.id        = {SEED_REPORT_ID}")
        print(f"  test_results     = {len(results)} rows")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
