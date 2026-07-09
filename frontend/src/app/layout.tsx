import type { Metadata } from "next";
import { AuthProvider } from "@/components/auth/AuthProvider";
import "./globals.css";
import "./newdesign.css";
import "./newdesign-enh.css";

export const metadata: Metadata = {
  title: "MITS — Math Intelligent Tutoring System",
  description: "Сократический STEM-репетитор на базе Qwen3.5-9B · BKT + DKT · Bauman MSTU",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      {/* new_design "midnight" theme. The `.app` grid fills the viewport; Geist
          fonts arrive via the @import at the top of newdesign.css. */}
      <body
        className="theme-midnight"
        style={{
          margin: 0,
          height: "100vh",
          background: "var(--bg)",
          // expose a mono var for inline styles in newdesign components
          ["--font-mono" as string]: "'Geist Mono', ui-monospace, monospace",
        }}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
