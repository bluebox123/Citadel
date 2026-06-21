import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400", "500", "600"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  colorScheme: "dark",
};

export const metadata: Metadata = {
  title: "GuardRail-AI | Cryptographic Security Gateway",
  description:
    "Advanced LLM firewall with prompt injection detection, HMAC-SHA256 payload signing, and grammar-strict output validation.",
  keywords: [
    "LLM",
    "security",
    "firewall",
    "prompt injection",
    "cryptography",
    "HMAC-SHA256",
    "CFG parsing",
    "gateway",
  ],
  authors: [{ name: "GuardRail-AI Team" }],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://guardrail-ai.example.com",
    title: "GuardRail-AI | Cryptographic Security Gateway",
    description:
      "Advanced LLM firewall with prompt injection detection and zero-trust architecture.",
    siteName: "GuardRail-AI",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const fontVars = [inter.variable, spaceGrotesk.variable, ibmPlexMono.variable].join(" ");

  return (
    <html lang="en" className={fontVars}>
      <head />
      <body className="bg-[#0a0a0a] text-white antialiased overflow-hidden">
        <div className="relative h-screen w-screen">
          {children}
        </div>
      </body>
    </html>
  );
}
