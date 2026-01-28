"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { submitReport } from "@/lib/api";

const ALLOWED_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
];
const MAX_SIZE_MB = 20;

export default function UploadForm() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [language, setLanguage] = useState("en");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setError("");
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!ALLOWED_TYPES.includes(selected.type)) {
      setError("Unsupported file type. Please upload a PDF, JPEG, or PNG.");
      return;
    }

    if (selected.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File too large. Maximum size: ${MAX_SIZE_MB} MB.`);
      return;
    }

    setFile(selected);
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
      const result = await submitReport(
        file,
        age ? parseInt(age, 10) : undefined,
        gender || undefined,
        language
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
      className="space-y-6 rounded-lg border bg-white p-6 shadow-sm"
    >
      <div>
        <h2 className="text-lg font-semibold text-gray-800">
          Upload Lab Report
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Upload your lab report (PDF, JPEG, or PNG) to get an educational
          interpretation.
        </p>
      </div>

      {/* File input */}
      <div>
        <label
          htmlFor="file"
          className="block text-sm font-medium text-gray-700"
        >
          Lab Report File *
        </label>
        <input
          id="file"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleFileChange}
          className="mt-1 block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-blue-700 hover:file:bg-blue-100"
        />
        {file && (
          <p className="mt-1 text-xs text-gray-400">
            {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
          </p>
        )}
      </div>

      {/* Age and Gender */}
      <div className="grid grid-cols-2 gap-4">
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
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="en">English</option>
          <option value="ur">Urdu</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={submitting || !file}
        className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Submitting..." : "Analyze Report"}
      </button>

      <p className="text-center text-xs text-gray-400">
        Max file size: {MAX_SIZE_MB} MB. Supported: PDF, JPEG, PNG.
      </p>
    </form>
  );
}
