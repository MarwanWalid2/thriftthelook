"use client";

import { MapPin } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type DeliveryLocationProps = {
  apiUrl: string;
  deliveryZip: string;
  onDeliveryZipChange: (value: string) => void;
};

export default function DeliveryLocation({
  apiUrl,
  deliveryZip,
  onDeliveryZipChange,
}: DeliveryLocationProps) {
  const [message, setMessage] = useState("Use your ZIP for a more accurate delivered price.");

  const resolveZip = useCallback(async (latitude: number, longitude: number): Promise<void> => {
    try {
      const query = new URLSearchParams({ latitude: String(latitude), longitude: String(longitude) });
      const response = await fetch(`${apiUrl}/api/location/zip?${query.toString()}`);
      const payload = (await response.json()) as { zip?: string };
      if (!response.ok || !payload.zip) {
        throw new Error("ZIP lookup failed");
      }
      onDeliveryZipChange(payload.zip);
      setMessage(`ZIP ${payload.zip} is set for eBay delivery estimates.`);
    } catch {
      setMessage("We could not find a US ZIP. You can enter one instead.");
    }
  }, [apiUrl, onDeliveryZipChange]);

  const useLocation = useCallback((): void => {
    if (!navigator.geolocation) {
      setMessage("Location is not available here. Enter a US ZIP instead.");
      return;
    }
    setMessage("Finding the delivery ZIP near you…");
    navigator.geolocation.getCurrentPosition(
      (position) => void resolveZip(position.coords.latitude, position.coords.longitude),
      () => {
        setMessage("Location was not shared. You can enter a ZIP instead.");
      },
      { enableHighAccuracy: false, maximumAge: 300_000, timeout: 10_000 },
    );
  }, [resolveZip]);

  useEffect(() => {
    if (deliveryZip) {
      return;
    }
    const prompt = window.setTimeout(useLocation, 350);
    return () => window.clearTimeout(prompt);
  }, [deliveryZip, useLocation]);

  return (
    <div className="mt-6 w-full rounded-2xl border border-kraft bg-white/90 p-3 text-left shadow-paper">
      <div className="flex items-start gap-2">
        <MapPin className="mt-0.5 shrink-0 text-rose" size={18} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <label className="block text-xs font-extrabold text-cocoa" htmlFor="delivery-zip">
            Delivery ZIP <span className="text-rose">for shipping</span>
          </label>
          <input
            id="delivery-zip"
            className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-white px-3 text-sm font-bold text-ink"
            value={deliveryZip}
            onChange={(event) => {
              const zip = event.target.value.replace(/\D/g, "").slice(0, 5);
              onDeliveryZipChange(zip);
              if (zip.length === 5) {
                setMessage(`ZIP ${zip} is set for eBay delivery estimates.`);
              }
            }}
            inputMode="numeric"
            autoComplete="postal-code"
            pattern="[0-9]{5}"
            placeholder="US ZIP"
          />
          <p className="mt-1 text-xs font-semibold text-cocoa" aria-live="polite">{message}</p>
        </div>
      </div>
    </div>
  );
}
