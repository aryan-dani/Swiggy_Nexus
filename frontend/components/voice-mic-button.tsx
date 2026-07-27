"use client";

import { Loader2, Mic, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getApiBase } from "@/lib/api";
import { nexusToast } from "@/lib/nexus-toast-bus";
import { cn } from "@/lib/utils";

type MicState = "idle" | "recording" | "transcribing";

/** Voice-to-Cart mic — records a note, transcribes via Groq Whisper, hands back text.
 *  WhatsApp voice notes are the production channel; this is the demo equivalent. */
export function VoiceMicButton({
  disabled,
  onTranscript,
  className,
}: {
  disabled?: boolean;
  onTranscript: (text: string) => void;
  className?: string;
}) {
  const [state, setState] = useState<MicState>("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => cleanupStream, [cleanupStream]);

  const transcribe = useCallback(
    async (blob: Blob) => {
      setState("transcribing");
      try {
        const form = new FormData();
        const ext = blob.type.includes("ogg") ? "ogg" : "webm";
        form.append("audio", blob, `voice-note.${ext}`);
        const res = await fetch(`${getApiBase()}/api/voice/transcribe`, {
          method: "POST",
          body: form,
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(json.detail || `Transcription failed (${res.status})`);
        }
        const text = String(json.transcript || "").trim();
        if (!text) throw new Error("Heard nothing — try again closer to the mic");
        nexusToast(`Voice → "${text.slice(0, 60)}${text.length > 60 ? "…" : ""}"`);
        onTranscript(text);
      } catch (e) {
        nexusToast(e instanceof Error ? e.message : "Voice transcription failed");
      } finally {
        setState("idle");
      }
    },
    [onTranscript]
  );

  const start = useCallback(async () => {
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      nexusToast("Mic not supported in this browser");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : undefined;
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        cleanupStream();
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        if (blob.size < 400) {
          nexusToast("Too short — hold the mic a moment longer");
          setState("idle");
          return;
        }
        void transcribe(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setState("recording");
      nexusToast("Recording… tap again to stop");
    } catch {
      nexusToast("Mic permission denied");
      cleanupStream();
    }
  }, [cleanupStream, transcribe]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
  }, []);

  return (
    <button
      type="button"
      disabled={disabled || state === "transcribing"}
      onClick={() => (state === "recording" ? stop() : void start())}
      aria-label={state === "recording" ? "Stop recording" : "Record voice note"}
      title="Voice-to-Cart · WhatsApp voice notes in production"
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors",
        state === "recording"
          ? "animate-pulse border-red-600 bg-red-100 text-red-700"
          : state === "transcribing"
            ? "border-violet-300 bg-violet-50 text-violet-700"
            : "border-black/20 bg-white text-slate-500 hover:text-black",
        className
      )}
    >
      {state === "recording" ? (
        <Square className="h-4 w-4 fill-current" aria-hidden />
      ) : state === "transcribing" ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <Mic className="h-4 w-4" aria-hidden />
      )}
    </button>
  );
}
