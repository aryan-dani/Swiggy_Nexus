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
  title: "Swiggy Nexus — Agent POC",
  description:
    "Demo assistant orchestrating mocked Swiggy MCP tools (Food, Instamart, Dineout). Not affiliated with Swiggy.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${jetbrains.variable} ${plusJakarta.variable} font-sans min-h-screen`}
      >
        <NexusToastHost />
        <NexusSessionProvider>{children}</NexusSessionProvider>
      </body>
    </html>
  );
}
