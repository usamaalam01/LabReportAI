"use client";

import type { ReportStatusResponse } from "@/types";
import { getDownloadUrl } from "@/lib/api";
import DisclaimerBanner from "./DisclaimerBanner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportViewProps {
  data: ReportStatusResponse;
}

export default function ReportView({ data }: ReportViewProps) {
  return (
    <div className="space-y-6">
      <DisclaimerBanner />

      {/* Markdown result */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        {data.result_markdown ? (
          <div className="prose prose-sm max-w-none text-gray-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {data.result_markdown}
            </ReactMarkdown>
          </div>
        ) : (
          <p className="text-gray-500">No analysis content available.</p>
        )}
      </div>

      {/* PDF download */}
      {data.result_pdf_url && (
        <div className="text-center">
          <a
            href={getDownloadUrl(data.job_id)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block rounded-md bg-green-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
          >
            Download PDF Report
          </a>
        </div>
      )}

      {/* Upload another */}
      <div className="text-center">
        <a
          href="/"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
        >
          Upload Another Report
        </a>
      </div>
    </div>
  );
}
