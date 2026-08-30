"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  fetchReport,
  type ReportResponse,
  type TestResultResponse,
} from "@/lib/api";

function statusTone(
  status: TestResultResponse["status"],
  row: TestResultResponse,
): {
  label: string;
  emoji: string;
  card: string;
  chip: string;
} {
  const qualitative =
    Boolean(row.value_text) &&
    row.reference_min == null &&
    row.reference_max == null;

  if (status === "HIGH") {
    return {
      label: "Higher than listed range",
      emoji: "🔴",
      card: "border-[#d96b5a]/40 bg-[#fdf3f0]",
      chip: "bg-[#d96b5a]/15 text-[#9a3b2e]",
    };
  }
  if (status === "LOW") {
    return {
      label: "Lower than listed range",
      emoji: "🟡",
      card: "border-[#d4a017]/35 bg-[#fff8e8]",
      chip: "bg-[#d4a017]/20 text-[#8a6a00]",
    };
  }
  return {
    label: qualitative ? "As reported on form" : "Within listed range",
    emoji: "🟢",
    card: "border-[#3a9b8f]/35 bg-[#eef8f6]",
    chip: "bg-[#3a9b8f]/15 text-[#0a4a4c]",
  };
}

function formatResultValue(row: TestResultResponse): string {
  if (row.value_text) {
    return `${row.value_text}${row.unit ? ` ${row.unit}` : ""}`.trim();
  }
  if (row.value != null) {
    return `${row.value}${row.unit ? ` ${row.unit}` : ""}`.trim();
  }
  return "—";
}

function explanationFor(
  report: ReportResponse,
  row: TestResultResponse,
): string {
  const hit = report.result_explanations?.find(
    (item: any) =>
      item.test_result_id === row.id ||
      item.biomarker === row.marker_name ||
      item.marker_name === row.marker_name,
  );
  if (hit?.explanation) {
    return hit.explanation;
  }

  const refStr =
    row.reference_min != null || row.reference_max != null
      ? `reference range of ${row.reference_min ?? "—"}–${row.reference_max ?? "—"} ${row.unit || ""}`.trim()
      : "listed range";

  if (row.status === "HIGH") {
    return `${row.marker_name} (${formatResultValue(row)}) is higher than the expected ${refStr}. Elevated results should be reviewed with your physician to evaluate underlying factors.`;
  }
  if (row.status === "LOW") {
    return `${row.marker_name} (${formatResultValue(row)}) is lower than the expected ${refStr}. Below-range results should be discussed with your doctor.`;
  }
  return `${row.marker_name} (${formatResultValue(row)}) is within typical normal reference parameters.`;
}

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const reportId = params.id;
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReport(reportId)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load report.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  const failed = report?.report_type === "parsing_failed";
  const ready =
    report?.report_type === "parsed" || report?.report_type === "explained";
  const pending = report?.report_type === "pending";

  const sortedResults = useMemo(() => {
    if (!report?.test_results) return [];
    const rank = { HIGH: 0, LOW: 1, NORMAL: 2 } as const;
    return [...report.test_results].sort(
      (a, b) => rank[a.status] - rank[b.status],
    );
  }, [report]);

  return (
    <main className="relative min-h-screen overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_80%_0%,#d7ebe8_0%,transparent_45%),linear-gradient(165deg,#eef6f5_0%,#e2eeec_55%,#d5e6e4_100%)]"
      />

      <div className="relative mx-auto max-w-3xl px-6 py-12 sm:px-10">
        <Link
          href="/upload"
          className="font-sans text-sm font-semibold tracking-wide text-brand transition hover:text-brand-deep"
        >
          ← Upload another
        </Link>

        <h1 className="mt-6 font-display text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          Your report
        </h1>

        <div
          className="mt-5 rounded-lg border border-[#d4a017]/30 bg-[#fff8e8] px-4 py-3 font-sans text-sm leading-relaxed text-foreground/80"
          role="note"
        >
          Educational tool only. MedExplain AI does not diagnose, prescribe, or
          replace a licensed clinician. Always discuss results with your doctor.
        </div>

        {error && (
          <p className="mt-6 font-sans text-sm text-accent" role="alert">
            {error}
          </p>
        )}

        {!error && !report && (
          <p className="mt-6 font-sans text-foreground/70">Loading report…</p>
        )}

        {report && (
          <div className="mt-8 space-y-8">
            {failed && (
              <section className="rounded-xl bg-mist/70 px-6 py-8" role="alert">
                <p className="font-display text-3xl text-accent">Parsing failed</p>
                <p className="mt-3 font-sans text-base leading-relaxed text-foreground/70">
                  We could not recover usable lab numbers from this file. Phone
                  photos of full-page forms often fail when the image is small,
                  blurry, or the lab block is not a clear table. Retake closer to
                  the Laboratory Investigation section, use good light, or upload
                  a lab PDF/JPG.
                </p>
                <p className="mt-3 font-sans text-sm text-foreground/60">
                  Tip: open{" "}
                  <a
                    className="text-brand underline-offset-2 hover:underline"
                    href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/reports/${report.id}/raw-text`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    OCR raw text
                  </a>{" "}
                  to see exactly what the camera text extractor read (if it looks
                  like gibberish, retake the photo).
                </p>
              </section>
            )}

            {pending && (
              <section className="rounded-xl bg-mist/70 px-6 py-8">
                <p className="font-display text-3xl text-brand-deep">Processing…</p>
              </section>
            )}

            {ready && report.ai_summary && (
              <section>
                <h2 className="font-display text-2xl font-semibold text-foreground">
                  Summary
                </h2>
                <p className="mt-3 font-sans text-base leading-relaxed text-foreground/80">
                  {report.ai_summary}
                </p>
              </section>
            )}

            {ready && sortedResults.length > 0 && (
              <section>
                <h2 className="font-display text-2xl font-semibold text-foreground">
                  Test results
                </h2>
                <p className="mt-1 font-sans text-sm text-foreground/60">
                  Tap a card to read a plain-language explanation.
                </p>
                <ul className="mt-4 space-y-3">
                  {sortedResults.map((row) => {
                    const tone = statusTone(row.status, row);
                    const open = openId === row.id;
                    const explanation = explanationFor(report, row);
                    return (
                      <li key={row.id}>
                        <button
                          type="button"
                          onClick={() => setOpenId(open ? null : row.id)}
                          className={`w-full rounded-xl border px-4 py-4 text-left transition ${tone.card} hover:-translate-y-0.5`}
                          aria-expanded={open}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-sans text-lg font-semibold text-foreground">
                                <span aria-hidden className="mr-2">
                                  {tone.emoji}
                                </span>
                                {row.marker_name}
                              </p>
                              <p className="mt-1 font-sans text-sm text-foreground/70">
                                {formatResultValue(row)}
                                {(row.reference_min != null ||
                                  row.reference_max != null) && (
                                  <span>
                                    {" "}
                                    · ref {row.reference_min ?? "—"}–
                                    {row.reference_max ?? "—"}
                                  </span>
                                )}
                              </p>
                            </div>
                            <span
                              className={`shrink-0 rounded-md px-2.5 py-1 font-sans text-xs font-semibold ${tone.chip}`}
                            >
                              {tone.label}
                            </span>
                          </div>
                          {open && (
                            <p className="mt-3 border-t border-[var(--line)] pt-3 font-sans text-sm leading-relaxed text-foreground/80">
                              {explanation}
                            </p>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}

            {ready &&
              report.doctor_questions &&
              report.doctor_questions.length > 0 && (
                <section>
                  <h2 className="font-display text-2xl font-semibold text-foreground">
                    Questions to ask your doctor
                  </h2>
                  <ol className="mt-4 list-decimal space-y-3 pl-5 font-sans text-base leading-relaxed text-foreground/80">
                    {report.doctor_questions.map((q) => (
                      <li key={q}>{q}</li>
                    ))}
                  </ol>
                </section>
              )}

            <p className="border-t border-[var(--line)] pt-5 font-sans text-sm text-foreground/55">
              Report status: {report.report_type}. Educational use only.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
