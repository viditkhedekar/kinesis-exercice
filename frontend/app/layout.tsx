import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import Providers from "@/components/Providers";
import { themeScript } from "@/components/ThemeProvider";

// Geist (UI) + Geist Mono (metrics) — self-hosted, a deliberate pairing rather
// than the Inter/JetBrains most tools converge on. The classes expose
// --font-geist-sans / --font-geist-mono, which globals.css maps onto the
// --font-sans / --font-mono tokens Tailwind reads.

export const metadata: Metadata = {
  title: "Kinesis — Movement Intelligence",
  description: "Biomechanics analysis of gym technique from video. Built for coaches and athletes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
