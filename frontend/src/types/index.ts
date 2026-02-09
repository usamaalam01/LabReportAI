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
  language: string | null;
}

export interface ErrorResponse {
  status: "error";
  code: number;
  message: string;
}

// Chat types
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatSuggestionsResponse {
  suggestions: string[];
  messages_remaining: number;
}

export interface ChatStreamDoneEvent {
  suggestions: string[];
  messages_remaining: number;
}

export interface ChatStreamTokenEvent {
  content: string;
}

export interface ChatStreamErrorEvent {
  message: string;
}
