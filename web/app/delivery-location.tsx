"use client";

import { MapPin } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export type DeliveryMarket = {
  marketplace: "EBAY_US" | "EBAY_GB" | "EBAY_DE" | "EBAY_AU";
  country: "US" | "GB" | "DE" | "AU";
  countryName: "United States" | "United Kingdom" | "Germany" | "Australia";
  currency: "USD" | "GBP" | "EUR" | "AUD";
};

export type DeliveryDetails = DeliveryMarket & { postalCode: string };

const photoMarkets: DeliveryMarket[] = [
  { marketplace: "EBAY_US", country: "US", countryName: "United States", currency: "USD" },
  { marketplace: "EBAY_GB", country: "GB", countryName: "United Kingdom", currency: "GBP" },
  { marketplace: "EBAY_DE", country: "DE", countryName: "Germany", currency: "EUR" },
  { marketplace: "EBAY_AU", country: "AU", countryName: "Australia", currency: "AUD" },
];

type DeliveryLocationProps = {
  apiUrl: string;
  delivery: DeliveryDetails;
  onDeliveryChange: (value: DeliveryDetails) => void;
};

function marketForId(marketplace: string): DeliveryMarket | undefined {
  return photoMarkets.find((market) => market.marketplace === marketplace);
}

export default function DeliveryLocation({ apiUrl, delivery, onDeliveryChange }: DeliveryLocationProps) {
  const [message, setMessage] = useState("We use your delivery country and postcode for eBay shipping estimates.");

  const resolveLocation = useCallback(async (latitude: number, longitude: number): Promise<void> => {
    try {
      const query = new URLSearchParams({ latitude: String(latitude), longitude: String(longitude) });
      const response = await fetch(`${apiUrl}/api/location?${query.toString()}`);
      const payload = (await response.json()) as Partial<DeliveryDetails>;
      const market = payload.marketplace ? marketForId(payload.marketplace) : undefined;
      if (!response.ok || !market || !payload.postalCode) throw new Error("Location lookup failed");
      onDeliveryChange({ ...market, postalCode: payload.postalCode });
      setMessage(`${market.countryName} selected from your location. Check the postcode, then search when ready.`);
    } catch {
      setMessage("Choose one of our photo-search countries and enter its delivery postcode.");
    }
  }, [apiUrl, onDeliveryChange]);

  const useLocation = useCallback((): void => {
    if (!navigator.geolocation) {
      setMessage("Location is not available here. Choose your delivery country instead.");
      return;
    }
    setMessage("Matching your location to an eBay marketplace…");
    navigator.geolocation.getCurrentPosition(
      (position) => void resolveLocation(position.coords.latitude, position.coords.longitude),
      () => setMessage("Location was not shared. Choose your delivery country instead."),
      { enableHighAccuracy: false, maximumAge: 300_000, timeout: 10_000 },
    );
  }, [resolveLocation]);

  useEffect(() => {
    if (delivery.postalCode) return;
    const prompt = window.setTimeout(useLocation, 350);
    return () => window.clearTimeout(prompt);
  }, [delivery.postalCode, useLocation]);

  return (
    <div className="rounded-2xl border border-kraft bg-white/90 p-4 text-left shadow-paper">
      <div className="flex items-start gap-2">
        <MapPin className="mt-0.5 shrink-0 text-rose" size={18} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <label className="block text-xs font-extrabold text-cocoa" htmlFor="delivery-country">Delivery country <span className="text-rose">for shipping</span></label>
          <select id="delivery-country" className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-white px-3 text-sm font-bold text-ink" value={delivery.marketplace} onChange={(event) => { const market = marketForId(event.target.value); if (market) onDeliveryChange({ ...market, postalCode: "" }); }}>
            {photoMarkets.map((market) => <option key={market.marketplace} value={market.marketplace}>{market.countryName}</option>)}
          </select>
          <label className="mt-3 block text-xs font-extrabold text-cocoa" htmlFor="delivery-postcode">Delivery postcode</label>
          <input id="delivery-postcode" className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-white px-3 text-sm font-bold text-ink" value={delivery.postalCode} onChange={(event) => onDeliveryChange({ ...delivery, postalCode: event.target.value.slice(0, 16) })} autoComplete="postal-code" placeholder={delivery.country === "US" ? "ZIP code" : "Postcode"} />
          <p className="mt-2 text-xs font-semibold text-cocoa" aria-live="polite">{message}</p>
          <p className="mt-2 border-t border-kraft/60 pt-2 text-xs font-semibold leading-5 text-cocoa">Photo matching is currently available in the United States, United Kingdom, Germany, and Australia.</p>
        </div>
      </div>
    </div>
  );
}
