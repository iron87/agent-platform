import { useMemo, useState } from "react";

interface ApiKeyFieldProps {
  value: string;
  onChange: (value: string) => void;
}

export function ApiKeyField({ value, onChange }: ApiKeyFieldProps) {
  const [revealed, setRevealed] = useState(false);

  const inputType = revealed ? "text" : "password";
  const buttonLabel = useMemo(() => (revealed ? "Hide" : "Reveal"), [revealed]);

  return (
    <label className="flex flex-col gap-1 text-sm text-slate-700">
      API key
      <div className="flex gap-2">
        <input
          className="w-full rounded-md border border-slate-300 px-3 py-2"
          type={inputType}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="sk-..."
        />
        <button
          className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium"
          type="button"
          onClick={() => setRevealed((prev) => !prev)}
        >
          {buttonLabel}
        </button>
      </div>
    </label>
  );
}
