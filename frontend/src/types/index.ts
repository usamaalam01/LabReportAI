export interface AnalyzeReportResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface ReportStatusResponse {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  result_markdown: string | null;
  result_pdf_url: string | null;
  error_message: string | null;
  created_at: string | null;
}

export interface ErrorResponse {
  status: "error";
  code: number;
  message: string;
}
