"use client";

type StyleProfileProps = {
  size: string;
  avoidColors: string;
  conditionFloor: string;
  onSizeChange: (value: string) => void;
  onAvoidColorsChange: (value: string) => void;
  onConditionChange: (value: string) => void;
};

const sizeOptions = [
  "No preference",
  "XXS",
  "XS",
  "S",
  "M",
  "L",
  "XL",
  "2XL",
  "3XL",
  "4XL",
  "5XL",
];

export default function StyleProfile({
  size,
  avoidColors,
  conditionFloor,
  onSizeChange,
  onAvoidColorsChange,
  onConditionChange,
}: StyleProfileProps) {
  return (
    <div className="mt-5 grid gap-3">
      <label className="text-xs font-extrabold text-cocoa">
        Your size
        <select
          className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-paper px-3 text-sm font-bold text-ink"
          value={size}
          onChange={(event) => onSizeChange(event.target.value)}
        >
          {sizeOptions.map((option) => <option key={option} value={option === "No preference" ? "unspecified" : option}>{option}</option>)}
        </select>
        <span className="mt-1 block font-medium">Vintage labels vary—always check measurements.</span>
      </label>
      <details>
        <summary className="cursor-pointer text-sm font-extrabold text-rose-deep marker:text-rose">
          Fine-tune results <span className="font-semibold text-cocoa">(optional)</span>
        </summary>
        <div className="mt-3 grid gap-3 rounded-2xl bg-sky/35 p-4 sm:grid-cols-2">
          <label className="text-xs font-extrabold text-cocoa">
            Avoid colors
            <input
              className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-paper px-3 text-sm font-bold text-ink"
              value={avoidColors}
              onChange={(event) => onAvoidColorsChange(event.target.value)}
              placeholder="e.g. neon green"
            />
          </label>
          <label className="text-xs font-extrabold text-cocoa">
            Condition floor
            <select
              className="mt-1 min-h-11 w-full rounded-xl border border-kraft bg-paper px-3 text-sm font-bold text-ink"
              value={conditionFloor}
              onChange={(event) => onConditionChange(event.target.value)}
            >
              <option value="any">Any condition</option>
              <option value="good">Good or better</option>
              <option value="very good">Very good or better</option>
            </select>
          </label>
        </div>
      </details>
    </div>
  );
}
