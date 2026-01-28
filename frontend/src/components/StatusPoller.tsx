"use client";

import { useEffect, useState, useCallback } from "react";
import { getReportStatus } from "@/lib/api";
import type { ReportStatusResponse } from "@/types";

const POLL_INTERVAL_MS = 3000;

interface StatusPollerProps {
  jobId: string;
  onComplete: (data: ReportStatusResponse) => void;
  onError: (message: string) => void;
}

export default function StatusPoller({
  jobId,
  onComplete,
  onError,
}: StatusPollerProps) {
  const [status, setStatus] = useState<string>("pending");

  const poll = useCallback(async () => {
    try {
      const data = await getReportStatus(jobId);
      setStatus(data.status);

      if (data.status === "completed") {
        onComplete(data);
        return true;
      }

      if (data.status === "failed") {
        onError(data.error_message || "Report analysis failed.");
        return true;
      }

      return false;
    } catch (err) {
      onError(
        err instanceof Error ? err.message : "Failed to check report status."
      );
      return true;
    }
  }, [jobId, onComplete, onError]);

  useEffect(() => {
    let cancelled = false;

    async function startPolling() {
      while (!cancelled) {
        const done = await poll();
        if (done || cancelled) break;
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      }
    }

    startPolling();

    return () => {
      cancelled = true;
    };
  }, [poll]);

  return (
    <div className="flex flex-col items-center space-y-4 py-12">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
      <p className="text-lg font-medium text-gray-700">
        {status === "pending" && "Your report is queued for analysis..."}
        {status === "processing" && "Analyzing your report..."}
      </p>
      <p className="text-sm text-gray-500">
        This usually takes a few seconds. Please wait.
      </p>
    </div>
  );
}
