import { useState } from "react";
import {
  BarChart3,
  ChevronDown,
  ChevronUp,
  Code2,
  Database,
  ExternalLink,
  Info,
} from "lucide-react";
import {
  ComparedFoodSummary,
  NhanesBenchmarkItem,
  NhanesContext,
} from "../types";

interface SourceLinksCardProps {
  foodA: ComparedFoodSummary;
  foodB: ComparedFoodSummary;
  nhanesContext?: NhanesContext | null;
  surveyCohorts?: NhanesBenchmarkItem[];
}

const NHANES_URL =
  "https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/overview.aspx?BeginYear=2017";

export function SourceLinksCard({
  foodA,
  foodB,
  nhanesContext,
  surveyCohorts = [],
}: SourceLinksCardProps) {
  const [activeTab, setActiveTab] = useState<"sources" | "survey">("sources");
  const [showRawJson, setShowRawJson] = useState(false);

  const items = [
    { slot: "Food A", accent: "blue", data: foodA },
    { slot: "Food B", accent: "emerald", data: foodB },
  ] as const;

  const nhanesSourceUrl = nhanesContext?.source_url || NHANES_URL;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
            <Database className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              3. Source Links &amp; Record Traceability
            </h2>
            <p className="text-xs text-slate-500">
              USDA FoodData Central, ICMR-NIN IFCT 2017, and CDC NHANES 2017–2018
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab("sources")}
              className={`rounded-md px-3 py-1 transition ${
                activeTab === "sources"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Source Records
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("survey")}
              className={`inline-flex items-center gap-1 rounded-md px-3 py-1 transition ${
                activeTab === "survey"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <BarChart3 className="h-3.5 w-3.5 text-indigo-600" />
              Observed Survey Statistics
            </button>
          </div>

          {activeTab === "sources" && (
            <button
              type="button"
              onClick={() => setShowRawJson((prev) => !prev)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
            >
              <Code2 className="h-3.5 w-3.5" />
              View Raw Source Record (JSON)
              {showRawJson ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>
      </div>

      {activeTab === "sources" ? (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            {items.map(({ slot, accent, data }) => (
              <div
                key={`${slot}-${data.food_id}`}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4"
              >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      accent === "blue"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-emerald-100 text-emerald-800"
                    }`}
                  >
                    {slot}
                  </span>
                  <span className="rounded-md border border-slate-200 bg-white px-2 py-0.5 font-mono text-xs font-medium text-slate-700">
                    ID: {data.food_id}
                  </span>
                </div>

                <h3 className="text-sm font-semibold text-slate-900">
                  {data.name}{" "}
                  <span className="text-xs font-normal text-slate-500">
                    ({data.state})
                  </span>
                </h3>

                <p className="mt-1 text-xs text-slate-600">
                  Source: <span className="font-medium">{data.source_name}</span>
                  {data.match_method ? ` • Match: ${data.match_method}` : ""}
                </p>

                {data.aliases.length > 0 && (
                  <p className="mt-1.5 text-xs text-slate-500">
                    Aliases: {data.aliases.slice(0, 4).join(", ")}
                  </p>
                )}

                <a
                  href={data.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                >
                  Open official source record
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            ))}

            {/* CDC NHANES 2017-2018 Benchmark Citation Card */}
            <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold text-indigo-800">
                  Population Benchmark
                </span>
                <span className="rounded-md border border-indigo-200 bg-white px-2 py-0.5 font-mono text-xs font-medium text-indigo-700">
                  {nhanesContext?.data_origin === "nhanes_xpt"
                    ? "XPT Live"
                    : "Cached Fallback"}
                </span>
              </div>

              <h3 className="text-sm font-semibold text-slate-900">
                CDC NHANES 2017–2018
              </h3>

              <p className="mt-1 text-xs text-slate-600">
                Cohort:{" "}
                <span className="font-medium">
                  {nhanesContext?.age_group || "all_adults"}
                </span>{" "}
                &bull; Activity:{" "}
                <span className="font-medium">
                  {nhanesContext?.activity_level || "all"}
                </span>
              </p>

              <p className="mt-1.5 text-xs text-slate-500">
                Observed adult Day 1 recall medians (DR1TOT_J); non-prescriptive.
              </p>

              <a
                href={nhanesSourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-700 hover:text-indigo-900 hover:underline"
              >
                Open CDC NHANES 2017–2018 overview
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>

          {showRawJson && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-900 p-4 text-xs text-slate-100">
              <div className="mb-2 flex items-center justify-between text-slate-400">
                <span className="font-mono">raw_per_100g_and_nhanes.json</span>
                <span>SQLite + ChromaDB + NHANES verified payload</span>
              </div>
              <pre className="max-h-72 overflow-auto font-mono leading-relaxed">
                {JSON.stringify(
                  {
                    food_a: foodA.per_100g_record,
                    food_b: foodB.per_100g_record,
                    nhanes_context: nhanesContext || null,
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          )}
        </>
      ) : (
        <div className="space-y-3">
          <div className="flex items-start gap-2 rounded-xl border border-indigo-200 bg-indigo-50/70 px-3.5 py-2.5 text-xs text-indigo-900">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
            <p>
              <strong>Read-Only Observed Survey Statistics (DIQ_J &amp; BPX_J):</strong>{" "}
              Descriptive public-health context from CDC NHANES 2017–2018 adult
              survey participants. Never used to diagnose users or prescribe
              clinical diets.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 font-semibold uppercase tracking-wide text-slate-600">
                  <th className="px-3 py-2">Age Cohort</th>
                  <th className="px-3 py-2">Activity Filter</th>
                  <th className="px-3 py-2">Sample (n)</th>
                  <th className="px-3 py-2">Median BMI (BMX_J)</th>
                  <th className="px-3 py-2">Median BP (BPX_J)</th>
                  <th className="px-3 py-2">Reported Diabetes % (DIQ_J)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(surveyCohorts.length > 0
                  ? surveyCohorts
                  : nhanesContext
                  ? [
                      {
                        age_group: nhanesContext.age_group,
                        activity_level: nhanesContext.activity_level,
                        bmi_range: nhanesContext.bmi_range,
                        sample_size: nhanesContext.sample_size ?? 0,
                        medians: nhanesContext.cohort_medians,
                        survey_statistics: nhanesContext.survey_statistics,
                        data_origin: nhanesContext.data_origin,
                        source_name: nhanesContext.source_name,
                        source_url: nhanesContext.source_url,
                      },
                    ]
                  : []
                ).map((cohort) => {
                  const stats = cohort.survey_statistics;
                  const isActive =
                    nhanesContext?.age_group === cohort.age_group;
                  return (
                    <tr
                      key={`${cohort.age_group}-${cohort.activity_level}`}
                      className={isActive ? "bg-indigo-50/50 font-medium" : ""}
                    >
                      <td className="px-3 py-2 font-mono text-slate-800">
                        {cohort.age_group}
                      </td>
                      <td className="px-3 py-2 text-slate-600">
                        {cohort.activity_level}
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-700">
                        {stats.sample_size}
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-700">
                        {stats.median_bmi ?? "N/A"}
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-700">
                        {stats.median_systolic_bp_mmhg ?? "N/A"} /{" "}
                        {stats.median_diastolic_bp_mmhg ?? "N/A"} mm Hg
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-700">
                        {stats.pct_self_reported_diabetes !== null &&
                        stats.pct_self_reported_diabetes !== undefined
                          ? `${stats.pct_self_reported_diabetes}%`
                          : "N/A"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
