"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useRef,
  useState,
  useTransition,
  type DragEvent,
} from "react";

import { uploadReportWithProgress } from "@/lib/api";

const ACCEPTED = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";
const MAX_BYTES = 15 * 1024 * 1024;

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [, startTransition] = useTransition();

  const chooseFile = useCallback((file: File | null | undefined) => {
    setError(null);
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError("File exceeds the 15MB size limit.");
      setSelected(null);
      return;
    }
    setSelected(file);
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      chooseFile(event.dataTransfer.files?.[0]);
    },
    [chooseFile],
  );

  const onUpload = async () => {
    if (!selected || uploading) return;
    setUploading(true);
    setProgress(0);
    setError(null);
    try {
      const result = await uploadReportWithProgress(selected, setProgress);
      startTransition(() => {
        router.push(`/reports/${result.report_id}`);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploading(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_10%,#d7ebe8_0%,transparent_50%),linear-gradient(165deg,#eef6f5_0%,#e2eeec_55%,#d5e6e4_100%)]"
      />

      <div className="relative mx-auto max-w-2xl px-6 py-16 sm:px-10">
        <Link
          href="/"
          className="font-sans text-sm font-semibold tracking-wide text-brand transition hover:text-brand-deep"
        >
          ← MedExplain AI
        </Link>

        <h1 className="mt-8 font-display text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          Upload report
        </h1>
        <p className="mt-3 max-w-lg font-sans text-base leading-relaxed text-foreground/70">
          PDF, JPG, or PNG up to 15MB. Files are stored securely for interpretation —
          this step does not diagnose anything.
        </p>

        <div
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setDragging(false);
          }}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`mt-10 cursor-pointer rounded-xl border-2 border-dashed px-6 py-16 text-center transition ${
            dragging
              ? "border-brand bg-brand/10"
              : "border-[var(--line)] bg-mist/60 hover:border-brand/50"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="hidden"
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
          <p className="font-display text-2xl text-foreground">
            {selected ? selected.name : "Drop your report here"}
          </p>
          <p className="mt-2 font-sans text-sm text-foreground/60">
            {selected
              ? `${(selected.size / (1024 * 1024)).toFixed(2)} MB — click to change`
              : "or click to browse"}
          </p>
        </div>

        {uploading && (
          <div className="mt-6" aria-live="polite">
            <div className="mb-2 flex justify-between font-sans text-sm text-foreground/70">
              <span>Uploading…</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[var(--line)]">
              <div
                className="h-full rounded-full bg-brand transition-[width] duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <p className="mt-4 font-sans text-sm text-accent" role="alert">
            {error}
          </p>
        )}

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <button
            type="button"
            disabled={!selected || uploading}
            onClick={onUpload}
            className="rounded-md bg-brand px-7 py-3.5 font-sans text-base font-semibold text-mist shadow-[0_10px_30px_rgba(15,107,109,0.28)] transition enabled:hover:-translate-y-0.5 enabled:hover:bg-brand-deep disabled:cursor-not-allowed disabled:opacity-45"
          >
            {uploading ? "Uploading…" : "Start upload"}
          </button>
          <p className="font-sans text-sm text-foreground/55">
            Educational use only — not a medical diagnosis.
          </p>
        </div>
      </div>
    </main>
  );
}
