import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Camera,
  Database,
  Layers,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { ComparisonTable } from "./components/ComparisonTable";
import { ExplanationCard } from "./components/ExplanationCard";
import { FinalReportCard } from "./components/FinalReportCard";
import { GuardrailBanner } from "./components/GuardrailBanner";
import { InputPanel } from "./components/InputPanel";
import { ModelVerdictCard } from "./components/ModelVerdictCard";
import { NutrientChart } from "./components/NutrientChart";
import { SourceLinksCard } from "./components/SourceLinksCard";
import {
  CompareResponse,
  FocusLens,
  NhanesBenchmarkItem,
  UserProfile,
} from "./types";

const ARCHITECTURE_LAYERS = [
  { id: "1", title: "1. Profile & Input", desc: "BMI + Image + Text", icon: Layers },
  { id: "2", title: "2. Vision AI", desc: "CLIP / MobileNetV2 / Gemini", icon: Camera },
  {
    id: "3",
    title: "3. RAG & Rules",
    desc: "SQLite + NHANES Rules",
    icon: Database,
  },
  {
    id: "4",
    title: "4. Verdict & Report",
    desc: "Non-Clinical Insights",
    icon: ShieldCheck,
  },
];

const INITIAL_USER_PROFILE: UserProfile = {
  age: 25,
  height_cm: 170,
  weight_kg: 68,
  activity_level: "active",
  health_contexts: ["general_wellness"],
  goal: "balanced",
};

function mapAgeToCohort(age: number): string {
  if (age <= 39) return "18-39";
  if (age <= 59) return "40-59";
  return "60+";
}

function mapActivityToNhanes(activity: UserProfile["activity_level"]): string {
  return activity === "active" ? "active" : "moderate_low";
}

export function App() {
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendCount, setBackendCount] = useState<number | null>(null);
  const [userProfile, setUserProfile] =
    useState<UserProfile>(INITIAL_USER_PROFILE);
  const [surveyCohorts, setSurveyCohorts] = useState<NhanesBenchmarkItem[]>([]);
  const lastInputRef = useRef<Record<string, unknown>>({
    query: "Compare 150g cooked quinoa vs 100g rolled oats",
  });

  const fetchSurveyCohorts = async (profile: UserProfile) => {
    try {
      const params = new URLSearchParams({
        age_group: mapAgeToCohort(profile.age),
        activity_level: mapActivityToNhanes(profile.activity_level),
      });
      const res = await fetch(`/api/nhanes/benchmarks?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.age_cohort_summary)) {
          setSurveyCohorts(data.age_cohort_summary);
        }
      }
    } catch {
      // Non-fatal background fetch
    }
  };

  const runComparison = async (
    payload: Record<string, unknown>,
    profileOverride?: UserProfile
  ) => {
    const activeProfile = profileOverride || userProfile;
    lastInputRef.current = payload;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          user_profile: activeProfile,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Comparison request failed.");
      }
      setResult(data as CompareResponse);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reach comparison backend."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleUserProfileChange = (next: UserProfile) => {
    setUserProfile(next);
    void fetchSurveyCohorts(next);
    if (result?.status === "ok" && lastInputRef.current) {
      void runComparison(lastInputRef.current, next);
    }
  };

  const handleSwitchObjectiveFromGuardrail = (
    suggestion: string,
    suggestedLens?: FocusLens | null
  ) => {
    const lensPatch: Partial<UserProfile> =
      suggestedLens === "sodium_potassium"
        ? {
            health_contexts: ["blood_pressure_awareness"],
            goal: "lower_sodium",
          }
        : suggestedLens === "carb_fiber"
        ? {
            health_contexts: ["blood_sugar_awareness"],
            goal: "higher_fiber_lower_sugar",
          }
        : suggestedLens === "protein_energy"
        ? {
            health_contexts: ["fitness_gym"],
            goal: "higher_protein",
          }
        : suggestedLens === "iron_calcium"
        ? {
            health_contexts: ["micronutrient_focus"],
            goal: "balanced",
          }
        : {};

    const nextProfile: UserProfile = {
      ...userProfile,
      ...lensPatch,
    };
    setUserProfile(nextProfile);
    void runComparison({ query: suggestion }, nextProfile);
  };

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          const info = await res.json();
          if (typeof info.food_count === "number") {
            setBackendCount(info.food_count);
          }
        }
      } catch {
        // Ignore initial health warning if backend is still starting
      }
    })();

    void fetchSurveyCohorts(INITIAL_USER_PROFILE);
    void runComparison(
      { query: "Compare 150g cooked quinoa vs 100g rolled oats" },
      INITIAL_USER_PROFILE
    );
  }, []);

  const activeProfileSummary = result?.rules_analysis?.profile_summary;
  const modelAssessment = result?.rules_analysis?.model_assessment;
  const suggestions = result?.rules_analysis?.suggestions || [];
  const finalReport = result?.rules_analysis?.final_report;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                <Sparkles className="h-3.5 w-3.5" />
                PS 132 • Food Nutrient Comparison Assistant
              </div>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                Food Nutrient Comparison Assistant
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                5-Step Pipeline: User Profile &amp; Vision AI + Hybrid RAG +
                Reference Rules Engine + Quality Verdict &amp; Final Report
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs text-slate-700">
              <Activity className="h-4 w-4 text-emerald-600" />
              <span>
                {backendCount !== null
                  ? `${backendCount} verified foods indexed`
                  : "SQLite + ChromaDB RAG"}
              </span>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {ARCHITECTURE_LAYERS.map((layer) => {
              const Icon = layer.icon;
              return (
                <div
                  key={layer.id}
                  className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2"
                >
                  <div className="rounded-lg bg-white p-1.5 text-purple-600 shadow-sm">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-slate-800">
                      {layer.title}
                    </p>
                    <p className="truncate text-[11px] text-slate-500">
                      {layer.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        <InputPanel
          loading={loading}
          userProfile={userProfile}
          onUserProfileChange={handleUserProfileChange}
          onCompareText={(query) => runComparison({ query })}
          onCompareMixed={(payload) => runComparison(payload)}
        />

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
          >
            {error}
          </div>
        )}

        <GuardrailBanner
          guardrail={result?.guardrail}
          onTrySuggestion={handleSwitchObjectiveFromGuardrail}
        />

        {result?.status === "ok" && result.comparison && (
          <div className="space-y-6">
            {/* Active Profile Summary Strip */}
            {activeProfileSummary && (
              <div
                data-testid="active-profile-strip"
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-purple-200 bg-purple-50/70 px-4 py-2.5 text-xs text-purple-950"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 font-semibold text-purple-800">
                    <UserCheck className="h-4 w-4 text-purple-600" />
                    Active Profile:
                  </span>
                  <span className="rounded-md bg-white px-2 py-0.5 font-medium shadow-sm">
                    Age {activeProfileSummary.age} ({activeProfileSummary.age_group})
                  </span>
                  <span className="rounded-md bg-white px-2 py-0.5 font-medium shadow-sm">
                    BMI {activeProfileSummary.bmi} ({activeProfileSummary.bmi_category})
                  </span>
                  <span className="rounded-md bg-white px-2 py-0.5 font-medium shadow-sm">
                    {activeProfileSummary.activity_label}
                  </span>
                  <span className="rounded-md bg-white px-2 py-0.5 font-medium shadow-sm">
                    Focus: {activeProfileSummary.health_context_labels.join(", ")}
                  </span>
                  <span className="rounded-md bg-white px-2 py-0.5 font-medium shadow-sm">
                    Goal: {activeProfileSummary.goal_label}
                  </span>
                </div>
              </div>
            )}

            {/* Model Prediction, Quality Score & Suggestions */}
            {modelAssessment && (
              <ModelVerdictCard
                foodA={result.comparison.food_a}
                foodB={result.comparison.food_b}
                assessment={modelAssessment}
                suggestions={suggestions}
              />
            )}

            <div className="grid gap-6 lg:grid-cols-12">
              <div className="lg:col-span-7">
                <ComparisonTable
                  foodA={result.comparison.food_a}
                  foodB={result.comparison.food_b}
                  rows={result.comparison.rows}
                  nhanesContext={result.comparison.nhanes_context}
                  rulesAnalysis={result.rules_analysis}
                />
              </div>
              <div className="lg:col-span-5">
                <NutrientChart
                  foodA={result.comparison.food_a}
                  foodB={result.comparison.food_b}
                  rows={result.comparison.rows}
                  focusLens={result.comparison.focus_lens}
                />
              </div>
            </div>

            {result.explanation && (
              <ExplanationCard
                text={result.explanation.text}
                profileContextSummary={
                  result.explanation.profile_context_summary
                }
                bulletPoints={result.explanation.bullet_points}
                provider={result.explanation.provider}
              />
            )}

            {finalReport && <FinalReportCard report={finalReport} />}

            <SourceLinksCard
              foodA={result.comparison.food_a}
              foodB={result.comparison.food_b}
              nhanesContext={result.comparison.nhanes_context}
              surveyCohorts={surveyCohorts}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
