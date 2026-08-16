import type { Metadata } from "next";

import { LandingPage } from "@/components/landing-page";

export const metadata: Metadata = {
  title: "Swiggy Nexus — One agent. Three verticals.",
  description:
    "Agentic copilot for Swiggy Food, Instamart, and Dineout. 44 MCP tools, HITL on every write, 60-second Chrono-Host WOW.",
  robots: { index: false, follow: false },
};

export default function Landing() {
  return <LandingPage />;
}
