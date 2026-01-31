"use client";

import { useState, useRef, type FormEvent, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import { submitReport } from "@/lib/api";

declare global {
  interface Window {
    grecaptcha?: {
      ready: (cb: () => void) => void;
      execute: (siteKey: string, options: { action: string }) => Promise<string>;
    };
  }
}

const ALLOWED_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
];
const MAX_SIZE_MB = 20;
const RECAPTCHA_SITE_KEY = process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY;

export default function UploadForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [language, setLanguage] = useState("en");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function validateFile(selectedFile: File): string | null {
    if (!ALLOWED_TYPES.includes(selectedFile.type)) {
      return "Unsupported file type. Please upload a PDF, JPEG, or PNG.";
    }

    if (selectedFile.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File too large. Maximum size: ${MAX_SIZE_MB} MB.`;
    }

    return null;
  }

  function handleFileSelection(selectedFile: File) {
    setError("");
    const validationError = validateFile(selectedFile);

    if (validationError) {
      setError(validationError);
      return;
    }

    setFile(selectedFile);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      handleFileSelection(selected);
    }
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelection(droppedFile);
    }
  }

  function handleDropZoneClick() {
    fileInputRef.current?.click();
  }

  function handleDropZoneKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!file) {
      setError("Please select a file to upload.");
      return;
    }

    setSubmitting(true);

    try {
      // Get reCAPTCHA token (if configured)
      let captchaToken: string | undefined;
      if (
        RECAPTCHA_SITE_KEY &&
        RECAPTCHA_SITE_KEY !== "placeholder" &&
        window.grecaptcha
      ) {
        try {
          captchaToken = await new Promise<string>((resolve) => {
            window.grecaptcha!.ready(() => {
              window
                .grecaptcha!.execute(RECAPTCHA_SITE_KEY!, { action: "submit" })
                .then(resolve);
            });
          });
        } catch {
          // reCAPTCHA not available — continue without token
        }
      }

      const result = await submitReport(
        file,
        age ? parseInt(age, 10) : undefined,
        gender || undefined,
        language,
        captchaToken
      );
      router.push(`/report/${result.job_id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred."
      );
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 rounded-lg border bg-white p-4 shadow-sm sm:p-6"
      aria-label="Lab report upload form"
    >
      <div>
        <h2 className="text-lg font-semibold text-gray-800 sm:text-xl">
          Upload Lab Report
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Upload your lab report (PDF, JPEG, or PNG) to get an educational
          interpretation.
        </p>
      </div>

      {/* Drag-and-drop zone */}
      <div>
        <label
          htmlFor="file"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          Lab Report File *
        </label>
        <div
          onClick={handleDropZoneClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onKeyDown={handleDropZoneKeyDown}
          tabIndex={0}
          role="button"
          aria-label="Upload file area - click or drag and drop to select file"
          className={`
            relative cursor-pointer rounded-lg border-2 border-dashed p-6 text-center
            transition-all duration-200 ease-in-out
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            ${
              isDragging
                ? "border-blue-500 bg-blue-50 scale-[1.02]"
                : file
                ? "border-green-300 bg-green-50 hover:bg-green-100"
                : "border-gray-300 hover:border-gray-400 hover:bg-gray-50"
            }
          `}
        >
          <input
            ref={fileInputRef}
            id="file"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFileChange}
            className="hidden"
            aria-label="File input"
          />

          {file ? (
            <div className="space-y-2">
              <svg
                className="mx-auto h-10 w-10 text-green-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-sm font-medium text-gray-700">{file.name}</p>
              <p className="text-xs text-gray-500">
                {(file.size / (1024 * 1024)).toFixed(1)} MB
              </p>
              <p className="text-xs text-gray-400">
                Click to change file
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                stroke="currentColor"
                fill="none"
                viewBox="0 0 48 48"
                aria-hidden="true"
              >
                <path
                  d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <div className="text-sm text-gray-600">
                <span className="font-semibold text-blue-600 hover:text-blue-700">
                  Click to upload
                </span>
                {" "}or drag and drop
              </div>
              <p className="text-xs text-gray-500">
                PDF, JPEG, or PNG up to {MAX_SIZE_MB} MB
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Age and Gender */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="age"
            className="block text-sm font-medium text-gray-700"
          >
            Age (optional)
          </label>
          <input
            id="age"
            type="number"
            min="1"
            max="120"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            placeholder="e.g. 35"
            aria-label="Patient age"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div>
          <label
            htmlFor="gender"
            className="block text-sm font-medium text-gray-700"
          >
            Gender (optional)
          </label>
          <select
            id="gender"
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            aria-label="Patient gender"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Select...</option>
            <option value="Male">Male</option>
            <option value="Female">Female</option>
            <option value="Other">Other</option>
          </select>
        </div>
      </div>

      {/* Language */}
      <div>
        <label
          htmlFor="language"
          className="block text-sm font-medium text-gray-700"
        >
          Output Language
        </label>
        <select
          id="language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          aria-label="Report output language"
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="en">English</option>
          <option value="ur">Urdu (اردو)</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-md bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={submitting || !file}
        aria-busy={submitting}
        aria-label={submitting ? "Submitting report" : "Analyze report"}
        className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Submitting..." : "Analyze Report"}
      </button>

      <p className="text-center text-xs text-gray-400">
        Max file size: {MAX_SIZE_MB} MB. Supported: PDF, JPEG, PNG.
      </p>
    </form>
  );
}
