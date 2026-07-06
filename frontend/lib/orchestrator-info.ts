import { normalizeApiBase } from "@/lib/api";

/** How Nexus routes chat — shown in the command center for reviewers. */
export type OrchestratorMode = "deterministic" | "groq" | "fastapi-deterministic";

export function getOrchestratorInfo(): {
  mode: OrchestratorMode;
  label: string;
  detail: string;
  llmModel: string | null;
} {
  const api = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL);
  const groqHint = process.env.NEXT_PUBLIC_GROQ_ENABLED === "true";

  if (!api) {
    return {
      mode: "deterministic",
      label: "Deterministic Planner",
      detail: "Planner → Executor → Synth on Next.js (no LLM). Repeatable Swiggy MCP choreography.",
      llmModel: null,
    };
  }

  if (groqHint) {
    return {
      mode: "groq",
      label: "Groq LLM + MCP tools",
      detail: "FastAPI orchestrator with llama-3.3-70b-versatile tool-calling (GROQ_API_KEY on Render).",
      llmModel: "llama-3.3-70b-versatile",
    };
  }

  return {
    mode: "fastapi-deterministic",
    label: "FastAPI · Deterministic",
    detail: "Python agent streams real mock MCP (/food, /im, /dineout). Add GROQ_API_KEY for LLM.",
    llmModel: null,
  };
}
