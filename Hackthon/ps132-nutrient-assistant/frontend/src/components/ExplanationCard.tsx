import { Bot, CheckCircle2 } from "lucide-react";

interface ExplanationCardProps {
  text: string;
  profileContextSummary?: string;
  bulletPoints?: string[];
  provider: string;
}

export function ExplanationCard({
  text,
  profileContextSummary,
  bulletPoints,
  provider,
}: ExplanationCardProps) {
  const providerLabel = provider.startsWith("gemini:")
    ? `Gemini (${provider.replace("gemini:", "")})`
    : "Deterministic Grounded Insights";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-purple-50 p-2 text-purple-600">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              2. Tailored Food Insights (Non-Clinical)
            </h2>
            <p className="text-xs text-slate-500">
              Grounded strictly in Rules Engine JSON &amp; NHANES observed survey medians
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-xs font-medium text-purple-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {providerLabel}
        </span>
      </div>

      {profileContextSummary || (bulletPoints && bulletPoints.length > 0) ? (
        <div className="space-y-3 rounded-xl border border-slate-100 bg-slate-50/70 p-4">
          {profileContextSummary && (
            <p className="rounded-lg border border-purple-100 bg-purple-50/70 px-3 py-2 text-xs font-medium leading-relaxed text-purple-950">
              {profileContextSummary}
            </p>
          )}
          {bulletPoints && bulletPoints.length > 0 && (
            <ul className="space-y-2 text-sm leading-relaxed text-slate-800">
              {bulletPoints.map((bullet, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-600" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="rounded-xl border border-slate-100 bg-slate-50/70 p-4 text-sm leading-relaxed text-slate-800">
          {text}
        </p>
      )}
    </div>
  );
}
