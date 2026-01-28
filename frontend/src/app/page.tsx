import UploadForm from "@/components/UploadForm";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">
          Lab Report Interpreter
        </h1>
        <p className="mt-2 text-gray-600">
          Upload your lab report to get an AI-powered educational
          interpretation with color-coded results, charts, and lifestyle tips.
        </p>
      </div>
      <UploadForm />
      <div className="rounded-md bg-amber-50 border border-amber-200 p-4 text-sm text-amber-800">
        <strong>Disclaimer:</strong> This tool provides educational insights and
        clinical associations only. It is not a diagnosis or treatment
        recommendation. Please consult a qualified physician.
      </div>
    </div>
  );
}
