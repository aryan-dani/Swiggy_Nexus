"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { callMcp } from "@/lib/mcp-client";
import {
  DEMO_SETTINGS_DEFAULTS,
  loadDemoSettings,
  saveDemoSettings,
  type NexusDemoSettings,
} from "@/lib/nexus-settings-storage";

const SESSION_KEY = "nexus-request-id";

export type NexusAddress = {
  addressId: string;
  label: string;
  fullAddress?: string;
  area?: string;
  city?: string;
};

type CartSnapshot = {
  foodTotal: number;
  imTotal: number;
  foodItems: number;
  imItems: number;
};

type NexusSessionValue = {
  requestId: string;
  settings: NexusDemoSettings;
  setSettings: (partial: Partial<NexusDemoSettings>) => void;
  addresses: NexusAddress[];
  selectedAddressId: string;
  setSelectedAddressId: (id: string) => void;
  carts: CartSnapshot;
  bookingsCount: number;
  activeFoodOrderId: string | null;
  activeImOrderId: string | null;
  lastBookingId: string | null;
  refreshAddresses: () => Promise<void>;
  refreshCarts: () => Promise<void>;
  refreshBookings: () => Promise<void>;
  /** Programmatically send a chat message (e.g. Chrono confirm buttons). */
  sendChat: (text: string) => void;
  setOnSendChat: (fn: ((text: string) => void) | undefined) => void;
};

const NexusSessionContext = createContext<NexusSessionValue | null>(null);

export function NexusSessionProvider({ children }: { children: ReactNode }) {
  const [settingsState, setSettingsState] = useState<NexusDemoSettings>(DEMO_SETTINGS_DEFAULTS);
  const [requestId, setRequestId] = useState("default-session");
  const [addresses, setAddresses] = useState<NexusAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState("addr_kp_001");
  const [carts, setCarts] = useState<CartSnapshot>({ foodTotal: 0, imTotal: 0, foodItems: 0, imItems: 0 });
  const [bookingsCount, setBookingsCount] = useState(0);
  const [activeFoodOrderId, setActiveFoodOrderId] = useState<string | null>(null);
  const [activeImOrderId, setActiveImOrderId] = useState<string | null>(null);
  const [lastBookingId, setLastBookingId] = useState<string | null>(null);
  const onSendChatRef = useRef<((text: string) => void) | undefined>();

  useEffect(() => {
    setSettingsState(loadDemoSettings());
    const stored = window.localStorage.getItem(SESSION_KEY);
    if (stored) setRequestId(stored);
    else {
      const id = crypto.randomUUID();
      window.localStorage.setItem(SESSION_KEY, id);
      setRequestId(id);
    }
  }, []);

  const setSettings = useCallback((partial: Partial<NexusDemoSettings>) => {
    setSettingsState(saveDemoSettings(partial));
  }, []);

  const settings = settingsState;

  const setOnSendChat = useCallback((fn: ((text: string) => void) | undefined) => {
    onSendChatRef.current = fn;
  }, []);

  const sendChat = useCallback((text: string) => {
    onSendChatRef.current?.(text);
  }, []);

  const refreshAddresses = useCallback(async () => {
    const res = await callMcp("food", "get_addresses", {}, requestId);
    if (res.success && res.data && typeof res.data === "object") {
      const rows = (res.data as { addresses?: NexusAddress[] }).addresses ?? [];
      setAddresses(rows);
      if (rows.length && !rows.find((a) => a.addressId === selectedAddressId)) {
        setSelectedAddressId(rows[0].addressId);
      }
    }
  }, [requestId, selectedAddressId]);

  const refreshCarts = useCallback(async () => {
    const [foodRes, imRes] = await Promise.all([
      callMcp("food", "get_food_cart", { addressId: selectedAddressId }, requestId),
      callMcp("im", "get_cart", {}, requestId),
    ]);
    const food = foodRes.success && foodRes.data ? (foodRes.data as Record<string, unknown>) : {};
    const im = imRes.success && imRes.data ? (imRes.data as Record<string, unknown>) : {};
    setCarts({
      foodTotal: Number(food.total ?? 0),
      imTotal: Number(im.total ?? 0),
      foodItems: Array.isArray(food.items) ? food.items.length : 0,
      imItems: Array.isArray(im.items) ? im.items.length : 0,
    });
  }, [requestId, selectedAddressId]);

  const refreshBookings = useCallback(async () => {
    const res = await callMcp("dineout", "get_booking_status", { bookingId: lastBookingId ?? "none" }, requestId);
    if (res.success) setBookingsCount((c) => Math.max(c, lastBookingId ? 1 : 0));
  }, [requestId, lastBookingId]);

  useEffect(() => {
    if (requestId) {
      void refreshAddresses();
      void Promise.all([
        callMcp("dineout", "get_saved_locations", {}, requestId),
        callMcp("im", "your_go_to_items", {}, requestId),
      ]);
    }
  }, [requestId, refreshAddresses]);

  useEffect(() => {
    void refreshCarts();
  }, [refreshCarts, selectedAddressId]);

  const value = useMemo(
    (): NexusSessionValue => ({
      requestId,
      settings,
      setSettings,
      addresses,
      selectedAddressId,
      setSelectedAddressId,
      carts,
      bookingsCount,
      activeFoodOrderId,
      activeImOrderId,
      lastBookingId,
      refreshAddresses,
      refreshCarts,
      refreshBookings,
      sendChat,
      setOnSendChat,
    }),
    [
      requestId,
      settings,
      setSettings,
      addresses,
      selectedAddressId,
      carts,
      bookingsCount,
      activeFoodOrderId,
      activeImOrderId,
      lastBookingId,
      refreshAddresses,
      refreshCarts,
      refreshBookings,
      sendChat,
      setOnSendChat,
    ]
  );

  return (
    <NexusSessionContext.Provider value={value}>{children}</NexusSessionContext.Provider>
  );
}

export function useNexusSession() {
  const ctx = useContext(NexusSessionContext);
  if (!ctx) throw new Error("useNexusSession must be used within NexusSessionProvider");
  return ctx;
}

export function useNexusSessionOptional() {
  return useContext(NexusSessionContext);
}
