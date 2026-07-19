"use client";

import {
  Check,
  ExternalLink,
  ImageUp,
  MapPin,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";

import DeliveryLocation, { DeliveryDetails } from "./delivery-location";
import { preparePhotoForUpload } from "./image-upload";

type Selection = {
  slot: string;
  id: string;
  title: string;
  price: string;
  shipping: string | null;
  total: string | null;
  match_score: number;
  reason: string;
  image_url: string | null;
  item_url: string | null;
  currency: string;
};

type OutfitResult = {
  state: "complete" | "partial" | "over_budget";
  total: string;
  match_score: number;
  missing_slots: string[];
  selections: Selection[];
  alternatives: AlternativeLook[];
};

type AlternativeLook = {
  total: string;
  selections: Selection[];
};

type OutfitPayload = {
  mode: "offline" | "live";
  notice: string;
  zip: string | null;
  budget: string;
  result: OutfitResult;
  narration?: { note: string; tradeoffs: string[] };
};

type Criteria = {
  photo: File;
  budget: number;
  delivery: DeliveryDetails;
  zip: string;
  size: string;
  avoidColors: string;
  conditionFloor: string;
};

type SearchRun = {
  id: number;
  criteria: Criteria;
  status: "searching" | "complete" | "failure";
  feed: string[];
  payload?: OutfitPayload;
  failure?: string;
};

const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");
const sizeOptions = ["No preference", "XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL"];
const progressSteps = ["Read the look", "Isolate pieces", "Search eBay", "Fit the budget", "Style the receipt"];

function money(value: string | number, currency = "USD"): string {
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function slotLabel(slot: string): string {
  return slot.split(":").at(-1)?.replaceAll("_", " ") ?? "piece";
}

function sameCriteria(left: Criteria, right: Criteria): boolean {
  return (
    left.photo.name === right.photo.name &&
    left.photo.size === right.photo.size &&
    left.budget === right.budget &&
    left.delivery.marketplace === right.delivery.marketplace &&
    left.delivery.postalCode === right.delivery.postalCode &&
    left.size === right.size &&
    left.avoidColors === right.avoidColors &&
    left.conditionFloor === right.conditionFloor
  );
}

export default function OutfitWorkbench() {
  const [photo, setPhoto] = useState<File | null>(null);
  const [budget, setBudget] = useState(120);
  const [delivery, setDelivery] = useState<DeliveryDetails>({
    marketplace: "EBAY_US",
    country: "US",
    countryName: "United States",
    currency: "USD",
    postalCode: "",
  });
  const [size, setSize] = useState("unspecified");
  const [avoidColors, setAvoidColors] = useState("");
  const [conditionFloor, setConditionFloor] = useState("any");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [preparingPhoto, setPreparingPhoto] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [run, setRun] = useState<SearchRun | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const runIdRef = useRef(0);

  const draftCriteria = useMemo<Criteria | null>(() => {
    if (!photo) {
      return null;
    }
    return { photo, budget, delivery, zip: delivery.postalCode, size, avoidColors, conditionFloor };
  }, [photo, budget, delivery, size, avoidColors, conditionFloor]);

  const photoPreviewUrl = useMemo(
    () => photo ? URL.createObjectURL(photo) : null,
    [photo],
  );

  const draftChanged = Boolean(
    run?.criteria && draftCriteria && !sameCriteria(run.criteria, draftCriteria),
  );

  useEffect(() => () => controllerRef.current?.abort(), []);

  useEffect(
    () => () => {
      if (photoPreviewUrl) {
        URL.revokeObjectURL(photoPreviewUrl);
      }
    },
    [photoPreviewUrl],
  );

  async function stagePhoto(nextPhoto: File): Promise<void> {
    controllerRef.current?.abort();
    setPreparingPhoto(true);
    setUploadError(null);
    setUploadMessage(null);
    try {
      const prepared = await preparePhotoForUpload(nextPhoto);
      setPhoto(prepared.photo);
      setRun(null);
      if (prepared.optimized) {
        setUploadMessage("Photo optimized for a reliable live search.");
      }
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "This image could not be prepared.",
      );
    } finally {
      setPreparingPhoto(false);
    }
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>): void {
    if (event.target.files?.[0]) {
      void stagePhoto(event.target.files[0]);
    }
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLElement>): void {
    event.preventDefault();
    setDragActive(false);
    if (event.dataTransfer.files[0]) {
      void stagePhoto(event.dataTransfer.files[0]);
    }
  }

  function cancelSearch(): void {
    controllerRef.current?.abort();
    setRun((current) => current ? { ...current, status: "failure", failure: "Search cancelled." } : current);
  }

  async function submitSearch(): Promise<void> {
    if (!draftCriteria || draftCriteria.delivery.postalCode.trim().length < 2) {
      return;
    }
    controllerRef.current?.abort();
    const id = runIdRef.current + 1;
    runIdRef.current = id;
    const controller = new AbortController();
    controllerRef.current = controller;
    const criteria = { ...draftCriteria };
    setRun({
      id,
      criteria,
      status: "searching",
      feed: [`Searching eBay ${criteria.delivery.countryName} for delivery to ${criteria.delivery.postalCode}.`],
    });
    window.requestAnimationFrame(() => {
      document.getElementById("results-heading")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    const form = new FormData();
    form.set("photo", criteria.photo);
    form.set("budget", String(criteria.budget));
    form.set("size", criteria.size);
    form.set("avoid_colors", criteria.avoidColors);
    form.set("condition_floor", criteria.conditionFloor);
    form.set("delivery_zip", criteria.delivery.postalCode);
    form.set("delivery_marketplace", criteria.delivery.marketplace);
    try {
      const response = await fetch(`${apiUrl}/api/outfit`, {
        method: "POST",
        body: form,
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(await requestFailureMessage(response));
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const event of events) {
          applySseEvent(id, event);
        }
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      const message = error instanceof Error ? error.message : "The look could not be built.";
      setRun((current) => current?.id === id ? { ...current, status: "failure", failure: message } : current);
    }
  }

  function applySseEvent(id: number, event: string): void {
    const name = event.match(/^event: (.+)$/m)?.[1];
    const rawData = event.match(/^data: (.+)$/m)?.[1];
    if (!name || !rawData) {
      return;
    }
    const payload = JSON.parse(rawData) as { message?: string } & OutfitPayload;
    if (name === "progress" && payload.message) {
      setRun((current) => current?.id === id ? { ...current, feed: [...current.feed, payload.message ?? ""] } : current);
    }
    if (name === "failure" && payload.message) {
      setRun((current) => current?.id === id ? { ...current, status: "failure", failure: payload.message } : current);
    }
    if (name === "complete") {
      setRun((current) => current?.id === id ? { ...current, status: "complete", payload } : current);
    }
  }

  const canSubmit = Boolean(
    draftCriteria
      && delivery.postalCode.trim().length >= 2
      && !preparingPhoto
      && run?.status !== "searching",
  );
  const submitLabel = run && draftChanged ? "Update my look" : "Find my look";

  return (
    <section className="mt-12 space-y-8" aria-label="Outfit search">
      <section className="paper-lift rounded-card border border-kraft bg-paper p-5 sm:p-8" aria-labelledby="criteria-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-hand text-2xl font-semibold text-rose-deep">build your search</p>
            <h2 id="criteria-heading" className="text-3xl font-extrabold tracking-tight text-ink">One photo, one buyable look</h2>
            <p className="mt-1 text-sm font-semibold text-cocoa">Set the constraints first. We only search when you ask.</p>
          </div>
          {run?.status === "complete" && !draftChanged && <span className="inline-flex items-center gap-1 rounded-full bg-sage/40 px-3 py-2 text-sm font-extrabold text-ink"><Check size={16} /> Results are current</span>}
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-2">
            <label
            className={`relative grid min-h-56 cursor-pointer place-items-center rounded-card border-2 border-dashed p-5 text-center transition ${dragActive ? "border-rose bg-blush/50" : "border-kraft bg-blush/20 hover:bg-blush/35"}`}
            onDragEnter={() => setDragActive(true)}
            onDragLeave={() => setDragActive(false)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleDrop}
            >
            {photo && photoPreviewUrl ? (
              <div className="relative w-full rounded-card bg-white p-3 text-left shadow-paper">
                <span className="washi-tape absolute -top-3 left-7 z-10 h-7 w-24 -rotate-3 bg-butter/90 shadow-tape" aria-hidden="true" />
                <div
                  className="h-52 rounded-xl bg-kraft/20 bg-contain bg-center bg-no-repeat sm:h-64"
                  role="img"
                  aria-label={`Preview of ${photo.name}`}
                  style={{ backgroundImage: `url(${photoPreviewUrl})` }}
                />
                <div className="mt-3 flex items-center gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sage text-ink"><Check size={18} /></span>
                  <div className="min-w-0"><p className="font-extrabold text-ink">Your outfit photo</p><p className="truncate text-sm font-semibold text-cocoa">{photo.name}</p></div>
                </div>
                <p className="mt-2 text-xs font-extrabold text-rose">Tap to choose another photo</p>
              </div>
            ) : (
              <div><span className="mx-auto grid size-14 place-items-center rounded-full bg-blush text-rose-deep"><ImageUp size={26} /></span><p className="mt-3 text-lg font-extrabold text-ink">{preparingPhoto ? "Preparing your photo" : "Drop an outfit photo"}</p><p className="mt-1 text-sm font-semibold text-cocoa">JPG, PNG, paste, or drag a screenshot. Up to 25 MB.</p></div>
            )}
              <input className="sr-only" type="file" accept="image/*" onChange={handleFile} />
            </label>
            {(uploadMessage || uploadError) && <p className={`text-sm font-bold ${uploadError ? "text-rose-deep" : "text-cocoa"}`} role="status">{uploadError ?? uploadMessage}</p>}
          </div>

          <div className="space-y-4">
            <DeliveryLocation apiUrl={apiUrl} delivery={delivery} onDeliveryChange={setDelivery} />
            <div>
              <div className="flex items-center justify-between"><label className="text-sm font-extrabold text-ink" htmlFor="budget">Total budget</label><output className="rounded-full bg-kraft px-3 py-1 text-lg font-extrabold text-ink">{money(budget, delivery.currency)}</output></div>
              <input id="budget" className="mt-3 w-full accent-rose" type="range" min="50" max="150" step="5" value={budget} onChange={(event) => setBudget(Number(event.target.value))} />
              <div className="mt-1 flex justify-between text-xs font-bold text-cocoa"><span>{money(50, delivery.currency)}</span><span>{money(150, delivery.currency)}</span></div>
            </div>
            <label className="block text-sm font-extrabold text-ink">Your size
              <select className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-white px-3 text-sm font-bold text-ink" value={size} onChange={(event) => setSize(event.target.value)}>{sizeOptions.map((option) => <option key={option} value={option === "No preference" ? "unspecified" : option}>{option}</option>)}</select>
            </label>
            <button className="inline-flex items-center gap-2 text-sm font-extrabold text-rose-deep" type="button" onClick={() => setAdvancedOpen((open) => !open)}><SlidersHorizontal size={16} /> {advancedOpen ? "Hide preferences" : "Fine-tune preferences"}</button>
            {advancedOpen && <div className="grid gap-4 rounded-2xl bg-sky/30 p-4 sm:grid-cols-2">
              <label className="text-xs font-extrabold text-cocoa">Avoid colors<input className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-white px-3 text-sm text-ink" value={avoidColors} onChange={(event) => setAvoidColors(event.target.value)} /></label>
              <label className="text-xs font-extrabold text-cocoa">Condition<select className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-white px-3 text-sm text-ink" value={conditionFloor} onChange={(event) => setConditionFloor(event.target.value)}><option value="any">Any condition</option><option value="good">Good or better</option><option value="very good">Very good or better</option></select></label>
            </div>}
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-kraft/60 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-semibold text-cocoa">{delivery.postalCode.trim().length >= 2 ? budget < 100 ? `At ${money(budget, delivery.currency)}, eBay shipping may leave room for only one piece. Try a higher budget for a 2–3 piece look.` : `Searches eBay ${delivery.countryName} for delivery to ${delivery.postalCode}; every displayed total includes shipping.` : `Add your ${delivery.countryName} delivery postcode for eBay shipping.`}</p>
          {run?.status === "searching" ? <button className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-rose px-5 text-base font-extrabold text-rose" type="button" onClick={cancelSearch}><X size={18} /> Cancel search</button> : <button className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-rose px-6 text-base font-extrabold text-ink hover:bg-rose-deep hover:text-white disabled:cursor-not-allowed disabled:opacity-50" type="button" disabled={!canSubmit} onClick={() => void submitSearch()}><Search size={18} /> {submitLabel}</button>}
        </div>
      </section>

      <section id="results-heading" className="scroll-mt-6" aria-live="polite">
        {run?.status === "searching" && <SearchProgress run={run} />}
        {run?.status === "failure" && <div className="rounded-card border border-blush bg-blush/30 p-6"><p className="font-extrabold text-ink">This look did not complete.</p><p className="mt-1 text-sm font-semibold text-cocoa">{run.failure}</p><p className="mt-3 text-sm font-bold text-rose-deep">Edit the criteria above, then try again.</p></div>}
        {run?.status === "complete" && run.payload && <Results run={run} />}
      </section>
    </section>
  );
}

async function requestFailureMessage(response: Response): Promise<string> {
  if (response.status === 413) {
    return "That photo is too large to send. Choose an image up to 25 MB and we will optimize it first.";
  }
  try {
    const payload = (await response.json()) as { detail?: string };
    if (response.status === 422 && payload.detail) {
      return payload.detail;
    }
  } catch {
    // The hosting layer can return an HTML error page for rejected uploads.
  }
  return "The outfit service did not return a stream.";
}

function SearchProgress({ run }: { run: SearchRun }) {
  return <div className="rounded-card border border-kraft bg-paper p-6"><p className="font-hand text-2xl font-semibold text-rose-deep">finding your look</p><p className="mt-1 font-extrabold text-ink">Searching eBay {run.criteria.delivery.countryName} for delivery to {run.criteria.delivery.postalCode}</p><ol className="mt-5 grid gap-3 sm:grid-cols-5">{progressSteps.map((step, index) => <li className={`rounded-xl p-3 text-sm font-extrabold ${index < run.feed.length ? "bg-sage/40 text-ink" : "bg-paper text-cocoa"}`} key={step}>{index + 1}. {step}</li>)}</ol><p className="mt-5 text-sm font-semibold text-cocoa">{run.feed.at(-1)}</p></div>;
}

function Results({ run }: { run: SearchRun }) {
  const { payload } = run;
  const result = payload?.result;
  const [activeLookIndex, setActiveLookIndex] = useState(0);
  const [optionsForSlot, setOptionsForSlot] = useState<string | null>(null);

  if (!payload || !result) return null;

  const looks = [{ total: result.total, selections: result.selections }, ...result.alternatives];
  const activeLook = looks[activeLookIndex] ?? looks[0];
  const state = activeLookIndex > 0
    ? `Alternative look ${activeLookIndex + 1} of ${looks.length}`
    : result.state === "complete"
      ? "Complete"
      : result.state === "over_budget"
        ? "Over budget"
        : `Partial — missing ${result.missing_slots.join(", ") || "pieces"}`;

  return (
    <div className="space-y-5">
      <div className="rounded-card bg-ink p-6 text-paper">
        <p className="font-hand text-2xl font-semibold text-butter">your rebuilt look</p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-extrabold">{activeLook.selections.length} pieces · {money(activeLook.total, run.criteria.delivery.currency)} delivered</h2>
            <p className="mt-1 font-semibold text-paper/80">{state} · eBay {run.criteria.delivery.countryName} delivery to {run.criteria.delivery.postalCode}</p>
          </div>
          <span className="rounded-full bg-sage px-3 py-2 text-sm font-extrabold text-ink">Budget {money(run.criteria.budget, run.criteria.delivery.currency)}</span>
        </div>
      </div>

      {looks.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 rounded-card border border-kraft bg-paper p-4">
          <p className="mr-2 text-sm font-extrabold text-ink">Complete look options</p>
          {looks.map((look, index) => (
            <button
              className={`min-h-10 rounded-full border px-3 text-sm font-extrabold ${activeLookIndex === index ? "border-rose bg-rose text-ink" : "border-kraft bg-white text-rose hover:bg-blush"}`}
              key={`${look.total}-${index}`}
              type="button"
              onClick={() => { setActiveLookIndex(index); setOptionsForSlot(null); }}
            >
              {index === 0 ? "Best match" : `Option ${index + 1}`} · {money(look.total)}
            </button>
          ))}
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {activeLook.selections.map((selection) => {
          const slotOptions = looks
            .map((look, index) => ({
              index,
              look,
              selection: look.selections.find((candidate) => candidate.slot === selection.slot),
            }))
            .filter((option) => option.index !== activeLookIndex && option.selection && option.selection.id !== selection.id);
          const isOpen = optionsForSlot === selection.slot;

          return (
            <article className="polaroid-card rounded-card bg-white p-3" key={`${activeLookIndex}-${selection.id}`}>
              <div className="h-48 rounded-xl bg-kraft/30 bg-cover bg-center" style={selection.image_url ? { backgroundImage: `url(${selection.image_url})` } : undefined} />
              <div className="mt-3 flex items-start justify-between gap-3">
                <div><p className="text-xs font-extrabold uppercase tracking-wide text-cocoa">{slotLabel(selection.slot)}</p><h3 className="mt-1 text-sm font-extrabold text-ink">{selection.title}</h3></div>
                <span className="rounded-full bg-sage/40 px-2 py-1 text-xs font-extrabold text-ink">{selection.match_score}%</span>
              </div>
              <p className="mt-3 rounded-lg bg-kraft px-3 py-2 text-sm font-extrabold text-ink">{money(selection.total ?? "0", selection.currency)} delivered</p>
              <p className="mt-1 text-xs font-semibold text-cocoa">{money(selection.price, selection.currency)} + {money(selection.shipping ?? "0", selection.currency)} shipping</p>
              <p className="mt-3 font-hand text-base font-semibold leading-5 text-rose-deep">{selection.reason}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {selection.item_url && <a className="inline-flex min-h-11 items-center gap-1 rounded-full border border-rose px-3 text-xs font-extrabold text-rose hover:bg-blush" href={selection.item_url} target="_blank" rel="noreferrer">View on eBay <ExternalLink size={14} /></a>}
                <button className="min-h-11 rounded-full border border-kraft px-3 text-xs font-extrabold text-ink hover:bg-butter/30" type="button" onClick={() => setOptionsForSlot(isOpen ? null : selection.slot)}>{slotOptions.length > 0 ? `Other options (${slotOptions.length})` : "Other options"}</button>
              </div>
              {isOpen && <div className="mt-3 space-y-2 rounded-xl bg-sky/30 p-3"><p className="text-xs font-extrabold text-cocoa">Switching always keeps a complete, solver-approved basket.</p>{slotOptions.length > 0 ? slotOptions.map((option) => option.selection && <button className="block w-full rounded-lg bg-white p-2 text-left text-xs font-bold text-ink hover:bg-blush" key={`${option.index}-${option.selection.id}`} type="button" onClick={() => { setActiveLookIndex(option.index); setOptionsForSlot(null); }}><span className="block truncate">{option.selection.title}</span><span className="mt-1 block text-rose-deep">View option {option.index + 1} · {money(option.look.total)} total</span></button>) : <p className="text-xs font-semibold text-cocoa">No other complete look fits this budget yet. Raise the cap or refine the search, then select Update my look.</p>}</div>}
            </article>
          );
        })}
      </div>
      {payload.narration && <details className="rounded-card border border-kraft bg-paper p-5"><summary className="cursor-pointer font-extrabold text-rose-deep">Why these picks</summary><p className="mt-3 font-semibold text-ink">{payload.narration.note}</p><ul className="mt-3 list-disc space-y-1 pl-5 text-sm font-semibold text-cocoa">{payload.narration.tradeoffs.map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}</ul></details>}
      <p className="text-xs font-semibold text-cocoa"><MapPin className="mr-1 inline" size={13} />{payload.notice}</p>
    </div>
  );
}

// Kept temporarily as a visual reference while the rebuilt results flow settles.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyResults({ run }: { run: SearchRun }) {
  const { payload } = run;
  const result = payload?.result;
  if (!payload || !result) return null;
  const state = result.state === "complete" ? "Complete" : result.state === "over_budget" ? "Over budget" : `Partial — missing ${result.missing_slots.join(", ") || "pieces"}`;
  return <div className="space-y-5"><div className="rounded-card bg-ink p-6 text-paper"><p className="font-hand text-2xl font-semibold text-butter">your rebuilt look</p><div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-2xl font-extrabold">{result.selections.length} of 3 pieces · {money(result.total)} delivered</h2><p className="mt-1 font-semibold text-paper/80">{state} · eBay shipping to ZIP {run.criteria.zip}</p></div><span className="rounded-full bg-sage px-3 py-2 text-sm font-extrabold text-ink">Budget {money(run.criteria.budget)}</span></div></div><div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{result.selections.map((selection) => <article className="polaroid-card rounded-card bg-white p-3" key={selection.id}><div className="h-48 rounded-xl bg-kraft/30 bg-cover bg-center" style={selection.image_url ? { backgroundImage: `url(${selection.image_url})` } : undefined} /><div className="mt-3 flex items-start justify-between gap-3"><div><p className="text-xs font-extrabold uppercase tracking-wide text-cocoa">{slotLabel(selection.slot)}</p><h3 className="mt-1 text-sm font-extrabold text-ink">{selection.title}</h3></div><span className="rounded-full bg-sage/40 px-2 py-1 text-xs font-extrabold text-ink">{selection.match_score}%</span></div><p className="mt-3 rounded-lg bg-kraft px-3 py-2 text-sm font-extrabold text-ink">{money(selection.total ?? "0")} delivered</p><p className="mt-1 text-xs font-semibold text-cocoa">{money(selection.price)} + {money(selection.shipping ?? "0")} shipping</p><p className="mt-3 font-hand text-base font-semibold leading-5 text-rose-deep">{selection.reason}</p>{selection.item_url && <a className="mt-4 inline-flex min-h-11 items-center gap-1 rounded-full border border-rose px-3 text-xs font-extrabold text-rose hover:bg-blush" href={selection.item_url} target="_blank" rel="noreferrer">View on eBay <ExternalLink size={14} /></a>}</article>)}</div>{payload.narration && <details className="rounded-card border border-kraft bg-paper p-5"><summary className="cursor-pointer font-extrabold text-rose-deep">Why these picks</summary><p className="mt-3 font-semibold text-ink">{payload.narration.note}</p><ul className="mt-3 list-disc space-y-1 pl-5 text-sm font-semibold text-cocoa">{payload.narration.tradeoffs.map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}</ul></details>}<p className="text-xs font-semibold text-cocoa"><MapPin className="mr-1 inline" size={13} />{payload.notice}</p></div>;
}
