"use client";

import { useState, useCallback } from "react";
import { useParams } from "next/navigation";
import StatusPoller from "@/components/StatusPoller";
import ReportView from "@/components/ReportView";
import type { ReportStatusResponse } from "@/types";

export default function ReportPage() {
  const params = useParams();
  const jobId = params.jobId as string;

  const [result, setResult] = useState<ReportStatusResponse | null>(null);
  const [error, setError] = useState<string>("");

  const handleComplete = useCallback((data: ReportStatusResponse) => {
    setResult(data);
  }, []);

  const handleError = useCallback((message: string) => {
    setError(message);
  }, []);

  if (error) {
    return (
      <div className="space-y-4">
        <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          <strong>Error:</strong> {error}
        </div>
        <div className="text-center">
          <a
            href="/"
            className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
          >
            Try Again
          </a>
        </div>
      </div>
    );
  }

  if (result) {
    return <ReportView data={result} />;
  }

  return <StatusPoller jobId={jobId} onComplete={handleComplete} onError={handleError} />;
}
