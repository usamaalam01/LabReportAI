import type { AnalyzeReportResponse, ReportStatusResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function submitReport(
  file: File,
  age?: number,
  gender?: string,
  language: string = "en"
): Promise<AnalyzeReportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (age) formData.append("age", String(age));
  if (gender) formData.append("gender", gender);
  formData.append("language", language);

  const res = await fetch(`${API_URL}/v1/analyze-report`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.message || "Failed to submit report.");
  }

  return res.json();
}

export async function getReportStatus(
  jobId: string
): Promise<ReportStatusResponse> {
  const res = await fetch(`${API_URL}/v1/status/${jobId}`);

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.message || "Failed to fetch report status.");
  }

  return res.json();
}

export function getDownloadUrl(jobId: string): string {
  return `${API_URL}/v1/download/${jobId}`;
}
