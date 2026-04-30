const EVENT = "nexus-demo-toast";

export function nexusToast(message: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(EVENT, { detail: message }));
}

export function getNexusToastEventName() {
  return EVENT;
}
