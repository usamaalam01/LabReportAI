"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import type { ReportStatusResponse } from "@/types";
import { getDownloadUrl } from "@/lib/api";
import DisclaimerBanner from "./DisclaimerBanner";
import ChatWidget, { type ChatWidgetRef } from "./ChatWidget";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportViewProps {
  data: ReportStatusResponse;
}

export default function ReportView({ data }: ReportViewProps) {
  const router = useRouter();
  const chatWidgetRef = useRef<ChatWidgetRef>(null);

  const handleOpenChat = () => {
    chatWidgetRef.current?.open();
  };

  return (
    <div className="space-y-6">
      <DisclaimerBanner />

      {/* Markdown result */}
      <div
        className="rounded-lg border bg-white p-4 shadow-sm sm:p-6"
        role="article"
        aria-label="Lab report analysis results"
      >
        {data.result_markdown ? (
          <div className="prose prose-sm max-w-none text-gray-700 sm:prose-base">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {data.result_markdown}
            </ReactMarkdown>
          </div>
        ) : (
          <p className="text-gray-500">No analysis content available.</p>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex flex-col space-y-3 sm:flex-row sm:space-y-0 sm:space-x-4 sm:justify-center">
        {/* PDF download */}
        {data.result_pdf_url && (
          <a
            href={getDownloadUrl(data.job_id)}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Download PDF report (opens in new tab)"
            className="inline-flex items-center justify-center rounded-md bg-green-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
          >
            <svg
              className="mr-2 h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            Download PDF Report
          </a>
        )}

        {/* Discuss your report - opens chat */}
        {data.status === "completed" && (
          <button
            onClick={handleOpenChat}
            aria-label="Open chat to discuss your lab report"
            className="inline-flex items-center justify-center rounded-md bg-purple-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
          >
            <svg
              className="mr-2 h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            Discuss your Report
          </button>
        )}

        {/* Upload another */}
        <button
          onClick={() => router.push("/")}
          aria-label="Upload another lab report"
          className="inline-flex items-center justify-center rounded-md border-2 border-blue-600 bg-white px-6 py-2.5 text-sm font-semibold text-blue-600 shadow-sm transition-colors hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          <svg
            className="mr-2 h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
            />
          </svg>
          Upload Another Report
        </button>
      </div>

      {/* Result metadata */}
      <div className="text-center text-xs text-gray-400">
        <p>Job ID: {data.job_id}</p>
        {data.language && (
          <p>Language: {data.language === "en" ? "English" : "Urdu (اردو)"}</p>
        )}
      </div>

      {/* Chat Widget - floating button to ask questions about results */}
      {data.status === "completed" && <ChatWidget ref={chatWidgetRef} jobId={data.job_id} />}
    </div>
  );
}
