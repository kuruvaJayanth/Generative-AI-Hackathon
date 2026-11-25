import { Focus, Tag } from "lucide-react";
import {
  ComparedFoodSummary,
  NhanesContext,
  NutrientComparisonRow,
  RulesAnalysis,
} from "../types";

interface ComparisonTableProps {
  foodA: ComparedFoodSummary;
  foodB: ComparedFoodSummary;
  rows: NutrientComparisonRow[];
  nhanesContext?: NhanesContext | null;
  rulesAnalysis?: RulesAnalysis | null;
}

function renderNhanesBadge(pct: number | null) {
  if (pct === null || pct === undefined) {
    return (
      <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 font-sans text-[10px] font-medium text-slate-500">
        N/A vs NHANES
      </span>
    );
  }
  return (
    <span className="mt-1 inline-block rounded bg-purple-50 px-1.5 py-0.5 font-sans text-[10px] font-medium text-purple-700">
      {pct}% of NHANES median
    </span>
  );
}

export function ComparisonTable({
  foodA,
  foodB,
  rows,
  nhanesContext,
  rulesAnalysis,
}: ComparisonTableProps) {
  const tagsA = rulesAnalysis?.food_tags?.food_a || [];
  const tagsB = rulesAnalysis?.food_tags?.food_b || [];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            1. Nutrient Comparison Table
          </h2>
          <p className="text-xs text-slate-500">
            Priority nutrients highlighted at top &bull; Cohort:{" "}
            {nhanesContext
              ? `${nhanesContext.age_group} (${nhanesContext.activity_level}, BMI ${nhanesContext.bmi_range})`
              : "NHANES 2017–2018"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 font-medium text-blue-700">
            <span className="h-2 w-2 rounded-full bg-blue-600" />
            A: {foodA.name} ({foodA.portion_g}g, {foodA.state})
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 font-medium text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-600" />
            B: {foodB.name} ({foodB.portion_g}g, {foodB.state})
          </span>
        </div>
      </div>

      {/* Deterministic Nutrient Profile Tags */}
      {(tagsA.length > 0 || tagsB.length > 0) && (
        <div className="mb-4 grid gap-2.5 sm:grid-cols-2">
          <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold text-blue-900">
              <Tag className="h-3 w-3 text-blue-600" />
              {foodA.name} — Reference Tags
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tagsA.map((tag) => (
                <span
                  key={`${tag.label}-${tag.metric_text}`}
                  title={tag.metric_text}
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                    tag.is_priority
                      ? "border-purple-300 bg-purple-100 text-purple-900"
                      : "border-blue-200 bg-white text-blue-800"
                  }`}
                >
                  {tag.label}
                  <span className="font-mono text-[10px] opacity-75">
                    ({tag.metric_text})
                  </span>
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold text-emerald-900">
              <Tag className="h-3 w-3 text-emerald-600" />
              {foodB.name} — Reference Tags
            </div>
            <div className="flex flex-wrap gap-1.5">
              {tagsB.map((tag) => (
                <span
                  key={`${tag.label}-${tag.metric_text}`}
                  title={tag.metric_text}
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                    tag.is_priority
                      ? "border-purple-300 bg-purple-100 text-purple-900"
                      : "border-emerald-200 bg-white text-emerald-800"
                  }`}
                >
                  {tag.label}
                  <span className="font-mono text-[10px] opacity-75">
                    ({tag.metric_text})
                  </span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
              <th className="rounded-tl-lg px-3 py-2.5">Nutrient</th>
              <th className="px-3 py-2.5 text-blue-700">
                Food A ({foodA.portion_g}g)
              </th>
              <th className="px-3 py-2.5 text-emerald-700">
                Food B ({foodB.portion_g}g)
              </th>
              <th className="px-3 py-2.5">Diff (A &minus; B)</th>
              <th className="px-3 py-2.5">% vs B</th>
              <th className="rounded-tr-lg px-3 py-2.5 text-purple-700">
                + NHANES % Benchmark
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => {
              const diffPositive =
                row.diff_a_minus_b !== null && row.diff_a_minus_b > 0;
              const diffNegative =
                row.diff_a_minus_b !== null && row.diff_a_minus_b < 0;
              const highlighted = row.is_focused || row.is_priority;

              return (
                <tr
                  key={row.key}
                  className={`transition ${
                    highlighted
                      ? "bg-purple-50/50 hover:bg-purple-50/80"
                      : "hover:bg-slate-50/70"
                  }`}
                >
                  <td
                    className={`px-3 py-2.5 font-medium text-slate-800 ${
                      highlighted ? "border-l-4 border-purple-600 pl-2" : ""
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span>{row.label}</span>
                      {highlighted && (
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-purple-100 px-1.5 py-0.5 text-[10px] font-semibold text-purple-800">
                          <Focus className="h-2.5 w-2.5" />
                          Priority
                        </span>
                      )}
                    </div>
                  </td>

                  <td
                    className={`px-3 py-2.5 font-mono text-sm ${
                      row.higher_in === "A"
                        ? "font-semibold text-blue-700"
                        : "text-slate-700"
                    }`}
                  >
                    <div>{row.food_a_display}</div>
                    {renderNhanesBadge(row.food_a_pct_nhanes_median)}
                  </td>

                  <td
                    className={`px-3 py-2.5 font-mono text-sm ${
                      row.higher_in === "B"
                        ? "font-semibold text-emerald-700"
                        : "text-slate-700"
                    }`}
                  >
                    <div>{row.food_b_display}</div>
                    {renderNhanesBadge(row.food_b_pct_nhanes_median)}
                  </td>

                  <td className="px-3 py-2.5 font-mono text-sm">
                    <span
                      className={`inline-block rounded-md px-2 py-0.5 text-xs font-medium ${
                        diffPositive
                          ? "bg-blue-50 text-blue-700"
                          : diffNegative
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {row.diff_display}
                    </span>
                  </td>

                  <td className="px-3 py-2.5 font-mono text-xs text-slate-600">
                    {row.pct_diff_display}
                  </td>

                  <td className="px-3 py-2.5 text-xs text-slate-700">
                    <div className="font-mono font-medium text-purple-900">
                      {row.nhanes_median_display}
                      <span className="ml-1 font-sans text-[10px] font-normal text-slate-500">
                        /day median
                      </span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-slate-600">
                      A:{" "}
                      <span className="font-semibold text-blue-700">
                        {row.food_a_pct_nhanes_median !== null
                          ? `${row.food_a_pct_nhanes_median}%`
                          : "N/A"}
                      </span>{" "}
                      &bull; B:{" "}
                      <span className="font-semibold text-emerald-700">
                        {row.food_b_pct_nhanes_median !== null
                          ? `${row.food_b_pct_nhanes_median}%`
                          : "N/A"}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
