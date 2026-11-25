import { Award, CheckCircle2, Lightbulb, Sparkles } from "lucide-react";
import { ComparedFoodSummary, ModelAssessment } from "../types";

interface ModelVerdictCardProps {
  foodA: ComparedFoodSummary;
  foodB: ComparedFoodSummary;
  assessment: ModelAssessment;
  suggestions: string[];
}

export function ModelVerdictCard({
  foodA,
  foodB,
  assessment,
  suggestions,
}: ModelVerdictCardProps) {
  const isWinnerA = assessment.recommended_choice === "food_a";
  const isWinnerB = assessment.recommended_choice === "food_b";

  return (
    <div className="rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-emerald-50 p-2 text-emerald-700">
            <Award className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Model Prediction, Quality Score &amp; Suggestions
            </h2>
            <p className="text-xs text-slate-500">
              Objective per-100 g nutrient density score aligned to your active profile
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
          <Sparkles className="h-3.5 w-3.5" />
          {assessment.verdict_badge}
        </span>
      </div>

      {/* Verdict Summary Banner */}
      <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
        <h3 className="text-sm font-bold text-emerald-950">
          {assessment.verdict_title}
        </h3>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-700">
          {assessment.verdict_summary}
        </p>
      </div>

      {/* Score Cards */}
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        {[
          {
            slot: "Food A",
            food: foodA,
            score: assessment.food_a_score,
            tier: assessment.food_a_tier,
            strengths: assessment.food_a_strengths,
            winner: isWinnerA,
            barColor: "bg-blue-600",
          },
          {
            slot: "Food B",
            food: foodB,
            score: assessment.food_b_score,
            tier: assessment.food_b_tier,
            strengths: assessment.food_b_strengths,
            winner: isWinnerB,
            barColor: "bg-emerald-600",
          },
        ].map((item) => (
          <div
            key={item.slot}
            className={`rounded-xl border p-3.5 ${
              item.winner
                ? "border-emerald-300 bg-emerald-50/30"
                : "border-slate-200 bg-slate-50/60"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  {item.slot}
                </span>
                <p className="truncate text-sm font-semibold text-slate-900">
                  {item.food.name}
                </p>
              </div>
              <div className="text-right">
                <span className="font-mono text-lg font-bold text-slate-900">
                  {item.score}
                  <span className="text-xs font-normal text-slate-500">/100</span>
                </span>
                <p className="text-[11px] font-medium text-emerald-700">
                  {item.tier}
                </p>
              </div>
            </div>

            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className={`h-full rounded-full transition-all ${item.barColor}`}
                style={{ width: `${item.score}%` }}
              />
            </div>

            {item.strengths.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {item.strengths.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-700"
                  >
                    <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Actionable Everyday Suggestions */}
      {suggestions.length > 0 && (
        <div className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-900">
            <Lightbulb className="h-4 w-4 text-amber-600" />
            Practical Suggestions for Your Selection
          </div>
          <ul className="space-y-1.5 text-sm text-slate-800">
            {suggestions.map((tip, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-600" />
                <span>{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
