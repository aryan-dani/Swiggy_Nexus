import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google";

import { NexusToastHost } from "@/components/nexus-toast-host";
import { NexusSessionProvider } from "@/lib/nexus-session-context";
import "./globals.css";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Swiggy Nexus — Agentic AI Demo",
  description:
    "An autonomous agentic copilot orchestrating Swiggy's Food, Instamart, and Dineout verticals via mocked MCP tools. Built for the Builders Club hackathon.",
  keywords: ["swiggy", "agentic ai", "mcp", "food delivery", "instamart", "dineout", "llm orchestration"],
  authors: [{ name: "Swiggy Builders Club" }],
  openGraph: {
    title: "Swiggy Nexus — Agentic AI Demo",
    description:
      "Watch an AI agent autonomously search restaurants, manage carts, and book tables across Swiggy's three verticals — all in one conversation.",
    type: "website",
    locale: "en_IN",
    siteName: "Swiggy Nexus",
  },
  twitter: {
    card: "summary_large_image",
    title: "Swiggy Nexus — Agentic AI Demo",
    description:
      "Autonomous AI copilot for Food, Instamart, and Dineout via mocked MCP tools.",
  },
  robots: {
    index: false, // Demo — don't index
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <meta name="theme-color" content="#ffffff" />
        <link rel="icon" href="/favicon.ico" sizes="any" />
      </head>
      <body
        className={`${inter.variable} ${jetbrains.variable} ${plusJakarta.variable} font-sans min-h-screen`}
      >
        <NexusToastHost />
        <NexusSessionProvider>{children}</NexusSessionProvider>
      </body>
    </html>
  );
}
