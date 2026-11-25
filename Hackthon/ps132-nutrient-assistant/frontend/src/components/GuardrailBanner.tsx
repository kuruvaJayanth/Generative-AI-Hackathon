import { AlertTriangle, ShieldAlert, ShieldCheck, Sparkles } from "lucide-react";
import { FocusLens, GuardrailPayload } from "../types";

interface GuardrailBannerProps {
  guardrail?: GuardrailPayload | null;
  onTrySuggestion?: (suggestion: string, lens?: FocusLens | null) => void;
}

const DEFAULT_DISCLAIMER =
  "Comparison data is based on USDA FDC, ICMR-NIN IFCT 2017, and CDC NHANES 2017–2018 observational survey medians. Not personalized clinical or medical dietary advice.";

export function GuardrailBanner({
  guardrail,
  onTrySuggestion,
}: GuardrailBannerProps) {
  const disclaimerText = guardrail?.disclaimer || DEFAULT_DISCLAIMER;
  const lensLabel = guardrail?.suggested_lens_label || "Objective";

  return (
    <div className="space-y-3">
      {guardrail?.blocked && (
        <div
          role="alert"
          className="rounded-2xl border border-amber-300 bg-amber-50 p-5 shadow-sm"
        >
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-amber-100 p-2 text-amber-700">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div className="flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-amber-950">
                  Pre-Retrieval Clinical Advice Guardrail Triggered
                </h3>
                {guardrail.reason_category && (
                  <span className="rounded-full bg-amber-200/80 px-2.5 py-0.5 text-xs font-medium text-amber-900">
                    {guardrail.reason_category.replace(/_/g, " ")}
                  </span>
                )}
              </div>
              <p className="text-sm leading-relaxed text-amber-900">
                {guardrail.message}
              </p>
              {guardrail.matched_signals.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-amber-800">
                  <span className="font-medium">Detected clinical terms:</span>
                  {guardrail.matched_signals.map((signal) => (
                    <span
                      key={signal}
                      className="rounded-md border border-amber-300 bg-white/70 px-2 py-0.5 font-mono"
                    >
                      {signal}
                    </span>
                  ))}
                </div>
              )}
              {guardrail.suggested_comparison && onTrySuggestion && (
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={() =>
                      onTrySuggestion(
                        guardrail.suggested_comparison!,
                        guardrail.suggested_lens
                      )
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg bg-amber-700 px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-amber-800"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Switch to Objective {lensLabel} Comparison
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-100/80 px-4 py-3 text-xs text-slate-700">
        {guardrail?.blocked ? (
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
        ) : (
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
        )}
        <p className="leading-relaxed">{disclaimerText}</p>
      </div>
    </div>
  );
}
