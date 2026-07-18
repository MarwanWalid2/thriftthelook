import {
  Image as ImageIcon,
  MapPin,
  Scissors,
  Search,
  ShoppingBag,
  Sparkles,
  WalletCards,
} from "lucide-react";

import OutfitWorkbench from "./outfit-workbench";

const steps = [
  { icon: Search, title: "Read the fit", detail: "We break your photo into buyable pieces." },
  { icon: ShoppingBag, title: "Search eBay", detail: "We match your delivery country and postcode to eBay shipping." },
  { icon: Scissors, title: "Fit the budget", detail: "A deterministic solver keeps the basket honest." },
];

const decisionPoints = [
  { icon: ImageIcon, label: "Photo" },
  { icon: MapPin, label: "Delivery" },
  { icon: WalletCards, label: "Budget" },
];

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col px-5 pb-16 pt-6 sm:px-8 lg:px-12">
      <header className="flex min-h-12 items-center justify-between gap-4" aria-label="ThriftTheLook home">
        <a className="inline-flex items-center gap-2 font-extrabold text-ink" href="#criteria-heading">
          <span className="grid size-10 place-items-center rounded-full bg-rose text-ink shadow-paper">
            <Scissors size={20} strokeWidth={2.5} />
          </span>
          <span className="text-lg tracking-tight">ThriftTheLook</span>
        </a>
        <span className="hidden rounded-full bg-butter px-4 py-2 text-sm font-extrabold text-ink sm:inline-flex">
          made for your next great find
        </span>
      </header>

      <section className="mt-10 grid gap-8 lg:mt-14 lg:grid-cols-2 lg:items-stretch lg:gap-10" aria-labelledby="hero-heading">
        <div className="flex flex-col gap-8 lg:min-h-[336px] lg:justify-between">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-sky px-4 py-2 text-sm font-extrabold text-ink">
              <Sparkles size={16} />A thrift companion for saved fits
            </p>
            <h1 id="hero-heading" className="mt-6 text-balance text-5xl font-extrabold leading-[0.96] tracking-tight text-ink sm:text-6xl xl:text-[4.5rem]">
              Screenshot the fit. <span className="text-rose-deep">Thrift the look.</span>
            </h1>
          </div>
          <p className="max-w-xl text-lg font-semibold leading-8 text-cocoa sm:text-xl">
            Turn one outfit photo into a secondhand basket you can actually buy, under one all-in budget.
          </p>
        </div>

        <aside className="corkboard paper-lift flex min-h-[336px] flex-col justify-between rounded-[24px] border-8 border-[#F3A257] p-7 text-paper sm:p-8" aria-label="How the search is scoped">
          <div>
            <p className="font-hand text-3xl font-semibold text-butter">one clear decision</p>
            <p className="mt-5 max-w-sm text-2xl font-extrabold leading-tight">Your photo + delivery location + budget.</p>
            <p className="mt-4 max-w-sm text-sm font-semibold leading-6 text-paper/85">No mystery searches. We only look when you press the button.</p>
          </div>
          <div className="grid grid-cols-3 gap-2 border-t border-paper/30 pt-5">
            {decisionPoints.map((point) => {
              const Icon = point.icon;
              return <div className="flex flex-col items-center gap-2 text-center" key={point.label}><span className="grid size-9 place-items-center rounded-full bg-paper/15"><Icon size={17} /></span><span className="text-xs font-extrabold tracking-wide text-paper/90">{point.label}</span></div>;
            })}
          </div>
        </aside>
      </section>

      <OutfitWorkbench />

      <section className="paper-lift mt-16 rounded-card bg-blush/25 px-6 py-8 sm:px-8 sm:py-10" aria-labelledby="steps-heading">
        <p className="font-hand text-2xl font-semibold text-rose-deep">a tiny treasure hunt</p>
        <h2 id="steps-heading" className="mt-1 text-xl font-extrabold text-ink">How your look comes together</h2>
        <ol className="mt-8 grid gap-8 md:grid-cols-3 md:gap-6">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return <li className="flex items-start gap-4" key={step.title}><span className="grid size-11 shrink-0 place-items-center rounded-full bg-paper text-rose-deep shadow-tape"><Icon size={20} /></span><div><p className="font-extrabold text-ink">{index + 1}. {step.title}</p><p className="mt-1 leading-6 text-cocoa">{step.detail}</p></div></li>;
          })}
        </ol>
      </section>
    </main>
  );
}
