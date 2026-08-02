"use client";

import { useCallback, useState } from "react";
import { Loader2, UtensilsCrossed, X } from "lucide-react";

import { getApiBase } from "@/lib/api";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

type GuestChip = { id: string; label: string; email: string; host?: boolean };
type Venue = {
  restaurant_id: string;
  name: string;
  area?: string;
  cuisines?: string[];
  costForTwo?: number;
  rating?: number;
};
type Slot = { label: string; slot_id?: string | null };

type WizardDraft = {
  wizard_id: string;
  step: string;
  guests: string[];
  guest_chips: GuestChip[];
  venue?: string | null;
  restaurant_id?: string | null;
  slot?: string | null;
  slot_id?: string | null;
  slots?: Slot[];
  venues?: Venue[];
};

export type NightOutWizardResult = {
  approval_request_id?: string;
  venue?: string;
  slot?: string;
  calendar_mock?: boolean;
  guest_count?: number;
  message?: string;
};

function apiUrl(path: string) {
  return `${getApiBase()}${path}`;
}

export function NightOutWizardPanel({
  open,
  onClose,
  onConfirmed,
}: {
  open: boolean;
  onClose: () => void;
  onConfirmed: (result: NightOutWizardResult) => void;
}) {
  const [draft, setDraft] = useState<WizardDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [venueQuery, setVenueQuery] = useState("Pune");
  const [uiStep, setUiStep] = useState<"guests" | "venue" | "slot" | "confirm">("guests");

  const api = useCallback(async (path: string, init?: RequestInit) => {
    const res = await fetch(apiUrl(path), {
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      ...init,
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = json.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.message || res.statusText || "Request failed";
      throw new Error(msg);
    }
    return json as WizardDraft & NightOutWizardResult;
  }, []);

  const bootstrap = useCallback(async () => {
    setBusy(true);
    try {
      const json = await api("/api/concierge/night-out/wizard/start", { method: "POST" });
      setDraft(json);
      setUiStep("guests");
      setVenueQuery("Pune");
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Wizard failed to start");
    } finally {
      setBusy(false);
    }
  }, [api]);

  // Start when opened
  if (open && !draft && !busy) {
    void bootstrap();
  }

  if (!open) return null;

  const chips = draft?.guest_chips || [];
  const hostId = chips.find((c) => c.host)?.id || "aryan";
  const selected = new Set(draft?.guests || []);

  const toggleGuest = (id: string) => {
    if (!draft || id === hostId) return;
    const next = selected.has(id)
      ? draft.guests.filter((g) => g !== id)
      : [...draft.guests, id];
    if (!next.includes(hostId)) next.unshift(hostId);
    setDraft({ ...draft, guests: next });
  };

  const saveGuests = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      const json = await api(`/api/concierge/night-out/wizard/${draft.wizard_id}/guests`, {
        method: "POST",
        body: JSON.stringify({ guests: draft.guests }),
      });
      setDraft(json);
      setUiStep("venue");
      const venues = await api(
        `/api/concierge/night-out/wizard/${draft.wizard_id}/venues?q=${encodeURIComponent(venueQuery || "Pune")}`
      );
      setDraft(venues);
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Could not save guests");
    } finally {
      setBusy(false);
    }
  };

  const searchVenues = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      const venues = await api(
        `/api/concierge/night-out/wizard/${draft.wizard_id}/venues?q=${encodeURIComponent(venueQuery || "Pune")}`
      );
      setDraft(venues);
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Venue search failed");
    } finally {
      setBusy(false);
    }
  };

  const pickVenue = async (v: Venue) => {
    if (!draft) return;
    setBusy(true);
    try {
      const json = await api(`/api/concierge/night-out/wizard/${draft.wizard_id}/venue`, {
        method: "POST",
        body: JSON.stringify({ restaurant_id: v.restaurant_id, name: v.name }),
      });
      setDraft(json);
      setUiStep("slot");
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Could not set venue");
    } finally {
      setBusy(false);
    }
  };

  const pickSlot = async (s: Slot) => {
    if (!draft) return;
    setBusy(true);
    try {
      const json = await api(`/api/concierge/night-out/wizard/${draft.wizard_id}/slot`, {
        method: "POST",
        body: JSON.stringify({ slot: s.label, slot_id: s.slot_id }),
      });
      setDraft(json);
      setUiStep("confirm");
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Could not set slot");
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!draft) return;
    setBusy(true);
    try {
      const json = await api(`/api/concierge/night-out/wizard/${draft.wizard_id}/confirm`, {
        method: "POST",
      });
      onConfirmed(json);
      setDraft(null);
      onClose();
    } catch (e) {
      nexusToast(e instanceof Error ? e.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  };

  const guestLabels = (draft?.guests || [])
    .map((id) => chips.find((c) => c.id === id)?.label || id)
    .join(", ");

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-lg rounded-xl border-2 border-black bg-white p-4 shadow-[6px_6px_0_0_#000]"
      >
        <button
          type="button"
          className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded border border-black/20"
          aria-label="Close"
          onClick={() => {
            setDraft(null);
            onClose();
          }}
        >
          <X className="h-4 w-4" />
        </button>

        <div className="mb-3 flex items-center gap-2 pr-8">
          <UtensilsCrossed className="h-4 w-4" />
          <h3 className="font-display text-sm font-black uppercase tracking-wide">
            Night out wizard
          </h3>
        </div>

        <div className="mb-3 flex gap-1 font-display text-[9px] font-black uppercase tracking-wider text-slate-500">
          {(["guests", "venue", "slot", "confirm"] as const).map((s) => (
            <span
              key={s}
              className={cn(
                "rounded border px-2 py-0.5",
                uiStep === s ? "border-black bg-amber-200 text-black" : "border-black/15"
              )}
            >
              {s}
            </span>
          ))}
        </div>

        {busy && !draft ? (
          <div className="flex items-center gap-2 py-8 text-sm text-slate-600">
            <Loader2 className="h-4 w-4 animate-spin" /> Starting…
          </div>
        ) : null}

        {uiStep === "guests" && draft && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">Who&apos;s coming? (Host Aryan is always included.)</p>
            <div className="flex flex-wrap gap-2">
              {chips.map((c) => {
                const on = selected.has(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    disabled={c.host || busy}
                    onClick={() => toggleGuest(c.id)}
                    className={cn(
                      "rounded-full border-2 px-3 py-1.5 font-mono text-xs",
                      on
                        ? "border-black bg-amber-200"
                        : "border-black/20 bg-white hover:bg-slate-50",
                      c.host && "opacity-80"
                    )}
                  >
                    {c.label}
                    {c.host ? " · host" : ""}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              disabled={busy || selected.size < 2}
              onClick={() => void saveGuests()}
              className="w-full rounded border-2 border-black bg-black px-3 py-2 font-display text-[11px] font-black uppercase text-white disabled:opacity-50"
            >
              Next · pick restaurant
            </button>
          </div>
        )}

        {uiStep === "venue" && draft && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">Search Dineout venues in Pune.</p>
            <div className="flex gap-2">
              <input
                value={venueQuery}
                onChange={(e) => setVenueQuery(e.target.value)}
                className="flex-1 rounded border border-black/20 px-2 py-1.5 text-sm"
                placeholder="Italian, 6 Digs, Baner…"
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void searchVenues()}
                className="rounded border-2 border-black bg-white px-3 py-1.5 font-display text-[10px] font-black uppercase"
              >
                Search
              </button>
            </div>
            <ul className="max-h-56 space-y-1.5 overflow-y-auto">
              {(draft.venues || []).map((v) => (
                <li key={v.restaurant_id}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void pickVenue(v)}
                    className="flex w-full flex-col items-start rounded border border-black/15 bg-slate-50 px-3 py-2 text-left hover:bg-amber-50"
                  >
                    <span className="font-sans text-sm font-medium">{v.name}</span>
                    <span className="font-mono text-[10px] text-slate-500">
                      {(v.cuisines || []).slice(0, 2).join(" · ")}
                      {v.area ? ` · ${v.area}` : ""}
                      {v.costForTwo ? ` · ₹${v.costForTwo} for 2` : ""}
                    </span>
                  </button>
                </li>
              ))}
              {(draft.venues || []).length === 0 && (
                <li className="text-sm text-slate-500">No venues — try another query.</li>
              )}
            </ul>
            <button
              type="button"
              className="text-xs text-slate-500 underline"
              onClick={() => setUiStep("guests")}
            >
              Back
            </button>
          </div>
        )}

        {uiStep === "slot" && draft && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Slots at <strong>{draft.venue}</strong>
            </p>
            <div className="flex flex-wrap gap-2">
              {(draft.slots || []).map((s) => (
                <button
                  key={`${s.label}-${s.slot_id || ""}`}
                  type="button"
                  disabled={busy}
                  onClick={() => void pickSlot(s)}
                  className="rounded border-2 border-black bg-white px-3 py-2 font-mono text-sm hover:bg-amber-100"
                >
                  {s.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="text-xs text-slate-500 underline"
              onClick={() => setUiStep("venue")}
            >
              Back
            </button>
          </div>
        )}

        {uiStep === "confirm" && draft && (
          <div className="space-y-3">
            <div className="rounded border border-black/15 bg-amber-50 px-3 py-2 text-sm">
              <p>
                <span className="font-display text-[10px] font-black uppercase text-slate-500">
                  Guests
                </span>
                <br />
                {guestLabels}
              </p>
              <p className="mt-2">
                <span className="font-display text-[10px] font-black uppercase text-slate-500">
                  Venue
                </span>
                <br />
                {draft.venue}
              </p>
              <p className="mt-2">
                <span className="font-display text-[10px] font-black uppercase text-slate-500">
                  Time
                </span>
                <br />
                {draft.slot}
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => void confirm()}
              className="flex w-full items-center justify-center gap-2 rounded border-2 border-black bg-amber-300 px-3 py-2.5 font-display text-[11px] font-black uppercase shadow-[3px_3px_0_0_#000] disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Create Calendar + stage for Approve
            </button>
            <button
              type="button"
              className="text-xs text-slate-500 underline"
              onClick={() => setUiStep("slot")}
            >
              Back
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
