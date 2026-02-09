import type { Metadata } from "next";
import Script from "next/script";
import Image from "next/image";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lab Report AI",
  description:
    "AI-powered lab report interpretation for educational insights.",
};

const recaptchaSiteKey = process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY;
const recaptchaEnabled =
  recaptchaSiteKey && recaptchaSiteKey !== "placeholder";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-gray-50 text-gray-900" suppressHydrationWarning>
        {recaptchaEnabled && (
          <Script
            src={`https://www.google.com/recaptcha/api.js?render=${recaptchaSiteKey}`}
            strategy="afterInteractive"
          />
        )}
        <header className="border-b bg-white shadow-sm">
          <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
            <a href="/" className="flex items-center">
              <Image
                src="/logo.png"
                alt="LabReportAI"
                width={480}
                height={120}
                priority
                className="h-16 w-auto sm:h-24"
              />
            </a>
            <span className="text-xs text-gray-500 sm:text-sm">
              Educational Insights Only
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        <footer className="border-t bg-white py-6 text-center text-sm text-gray-500">
          <p>
            This tool provides educational insights only. It is not a diagnosis
            or treatment recommendation.
          </p>
          <p className="mt-2">
            Developed by{" "}
            <a
              href="mailto:queryversity@gmail.com"
              className="text-blue-600 hover:underline"
            >
              QueryVersity
            </a>
          </p>
        </footer>
      </body>
    </html>
  );
}
