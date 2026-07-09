import type { Metadata } from "next";
import { JetBrains_Mono, Space_Grotesk } from "next/font/google";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { ThemeProvider } from "@/components/cyber/ThemeProvider";
import { Scene } from "@/components/cyber/Scene";
import { Particles } from "@/components/cyber/Particles";
import "./globals.css";

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  variable: "--font-jetbrains-mono",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

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
    <html lang="ru" className="dark" data-theme="grimoire" data-glitch="on" suppressHydrationWarning>
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
          crossOrigin="anonymous"
        />
      </head>
      <body
        className={`${jetbrainsMono.variable} ${spaceGrotesk.variable} antialiased crt`}
      >
        <Scene />
        <Particles enabled={true} />
        <ThemeProvider>
          <AuthProvider>
            <div className="relative z-10 h-screen flex flex-col">
              {children}
            </div>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
