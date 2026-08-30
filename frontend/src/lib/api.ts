export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
};

export type UploadResponse = {
  report_id: string;
  file_url: string;
};

export type TestResultResponse = {
  id: string;
  report_id: string;
  marker_name: string;
  value: number | null;
  value_text?: string | null;
  unit: string;
  reference_min: number | null;
  reference_max: number | null;
  status: "NORMAL" | "HIGH" | "LOW";
};

export type ResultExplanation = {
  test_result_id: string;
  explanation: string;
};

export type ReportResponse = {
  id: string;
  user_id: string;
  file_url: string;
  report_type: string;
  ai_summary: string | null;
  result_explanations: ResultExplanation[] | null;
  doctor_questions: string[] | null;
  created_at: string;
  test_results: TestResultResponse[];
};

export function uploadReportWithProgress(
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/v1/upload`);
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const percent = Math.round((event.loaded / event.total) * 100);
      onProgress(percent);
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as UploadResponse);
        return;
      }
      const body = xhr.response as ApiErrorBody | null;
      const message =
        body?.error?.message || `Upload failed (${xhr.status}). Please try again.`;
      reject(new Error(message));
    };

    xhr.onerror = () => {
      reject(new Error("Network error while uploading. Is the backend running?"));
    };

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export async function fetchReport(reportId: string): Promise<ReportResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/reports/${reportId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiErrorBody | null;
    throw new Error(body?.error?.message || `Failed to load report (${res.status}).`);
  }
  return res.json() as Promise<ReportResponse>;
}
