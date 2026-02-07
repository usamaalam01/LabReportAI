import type { AnalyzeReportResponse, ReportStatusResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export async function submitReport(
  file: File,
  age?: number,
  gender?: string,
  language: string = "en",
  captchaToken?: string
): Promise<AnalyzeReportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (age) formData.append("age", String(age));
  if (gender) formData.append("gender", gender);
  formData.append("language", language);
  if (captchaToken) formData.append("captcha_token", captchaToken);

  let res: Response;
  try {
    res = await fetch(`${API_URL}/v1/analyze-report`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error("Network error. Please check your connection and try again.");
  }

  if (!res.ok) {
    let errorMessage = "Failed to submit report.";
    try {
      const error = await res.json();
      errorMessage = error.message || errorMessage;
    } catch {
      // Response body is empty or not valid JSON
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        errorMessage = "Server is temporarily unavailable. Please try again later.";
      } else if (res.status === 500) {
        errorMessage = "An internal server error occurred. Please try again later.";
      } else {
        errorMessage = `Server error (${res.status}). Please try again.`;
      }
    }
    throw new Error(errorMessage);
  }

  try {
    return await res.json();
  } catch {
    throw new Error("Invalid response from server. Please try again.");
  }
}

export async function getReportStatus(
  jobId: string
): Promise<ReportStatusResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/v1/status/${jobId}`);
  } catch {
    throw new Error("Network error. Please check your connection and try again.");
  }

  if (!res.ok) {
    let errorMessage = "Failed to fetch report status.";
    try {
      const error = await res.json();
      errorMessage = error.message || errorMessage;
    } catch {
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        errorMessage = "Server is temporarily unavailable. Please try again later.";
      } else if (res.status === 500) {
        errorMessage = "An internal server error occurred. Please try again later.";
      } else {
        errorMessage = `Server error (${res.status}). Please try again.`;
      }
    }
    throw new Error(errorMessage);
  }

  try {
    return await res.json();
  } catch {
    throw new Error("Invalid response from server. Please try again.");
  }
}

export function getDownloadUrl(jobId: string): string {
  return `${API_URL}/v1/download/${jobId}`;
}
