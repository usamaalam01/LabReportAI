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

// Processing steps with estimated durations (for progress simulation)
const PROCESSING_STEPS = [
  { label: "Extracting text from document...", duration: 3000 },
  { label: "Validating document...", duration: 5000 },
  { label: "Analyzing lab report...", duration: 12000 },
  { label: "Generating charts...", duration: 3000 },
  { label: "Creating PDF report...", duration: 4000 },
];

export default function StatusPoller({
  jobId,
  onComplete,
  onError,
}: StatusPollerProps) {
  const [status, setStatus] = useState<string>("pending");
  const [currentStep, setCurrentStep] = useState(0);
  const [elapsedTime, setElapsedTime] = useState(0);

  const poll = useCallback(async () => {
    try {
      const data = await getReportStatus(jobId);
      setStatus(data.status);

      if (data.status === "completed") {
        setCurrentStep(PROCESSING_STEPS.length);
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

  // Simulate progress based on elapsed time
  useEffect(() => {
    if (status !== "processing") return;

    const interval = setInterval(() => {
      setElapsedTime((prev) => prev + 1000);
    }, 1000);

    return () => clearInterval(interval);
  }, [status]);

  // Update current step based on elapsed time
  useEffect(() => {
    if (status !== "processing") return;

    let totalDuration = 0;
    for (let i = 0; i < PROCESSING_STEPS.length; i++) {
      totalDuration += PROCESSING_STEPS[i].duration;
      if (elapsedTime < totalDuration) {
        setCurrentStep(i);
        break;
      }
    }

    // Cap at last step
    if (elapsedTime >= totalDuration) {
      setCurrentStep(PROCESSING_STEPS.length - 1);
    }
  }, [elapsedTime, status]);

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

  const progressPercentage = status === "processing"
    ? Math.min(95, ((currentStep + 1) / PROCESSING_STEPS.length) * 100)
    : status === "pending"
    ? 0
    : 100;

  return (
    <div
      className="flex flex-col items-center space-y-6 py-8 sm:py-12"
      role="status"
      aria-live="polite"
      aria-label="Processing status"
    >
      {/* Progress bar */}
      <div className="w-full max-w-md px-4">
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-1000 ease-out"
            style={{ width: `${progressPercentage}%` }}
            aria-valuenow={progressPercentage}
            aria-valuemin={0}
            aria-valuemax={100}
            role="progressbar"
          />
        </div>
      </div>

      {/* Spinner */}
      <div
        className="h-10 w-10 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600"
        aria-hidden="true"
      />

      {/* Status text */}
      <div className="text-center">
        <p className="text-base font-medium text-gray-800 sm:text-lg">
          {status === "pending" && "Your report is queued for analysis..."}
          {status === "processing" && currentStep < PROCESSING_STEPS.length
            ? PROCESSING_STEPS[currentStep].label
            : "Finalizing report..."}
        </p>
        <p className="mt-2 text-sm text-gray-500">
          This usually takes 10-30 seconds. Please wait.
        </p>
      </div>

      {/* Steps indicator */}
      {status === "processing" && (
        <div className="flex flex-col space-y-2 w-full max-w-md px-4">
          {PROCESSING_STEPS.map((step, index) => (
            <div
              key={index}
              className={`flex items-center space-x-2 text-sm transition-opacity ${
                index <= currentStep ? "opacity-100" : "opacity-30"
              }`}
            >
              {index < currentStep ? (
                <svg
                  className="h-5 w-5 text-green-500 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : index === currentStep ? (
                <svg
                  className="h-5 w-5 text-blue-500 flex-shrink-0 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              ) : (
                <svg
                  className="h-5 w-5 text-gray-300 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
              <span
                className={`${
                  index === currentStep
                    ? "font-medium text-gray-900"
                    : "text-gray-600"
                }`}
              >
                {step.label.replace("...", "")}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
