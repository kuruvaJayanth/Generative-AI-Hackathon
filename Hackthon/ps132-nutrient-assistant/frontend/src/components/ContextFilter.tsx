import { Activity, Ruler, Scale, SlidersHorizontal, Target, User } from "lucide-react";
import {
  HealthContextKey,
  ProfileActivityLevel,
  ProfileGoalKey,
  UserProfile,
} from "../types";

interface ContextFilterProps {
  profile: UserProfile;
  onChange: (next: UserProfile) => void;
}

const ACTIVITY_OPTIONS: { value: ProfileActivityLevel; label: string }[] = [
  { value: "low", label: "Low / Sedentary" },
  { value: "moderate", label: "Moderate" },
  { value: "active", label: "Active / Gym & Fitness" },
];

const HEALTH_CONTEXT_OPTIONS: {
  value: HealthContextKey;
  label: string;
  hint: string;
}[] = [
  {
    value: "general_wellness",
    label: "General Wellness",
    hint: "Balanced macros",
  },
  {
    value: "blood_sugar_awareness",
    label: "Blood Sugar Awareness",
    hint: "Carbs, Sugars, Fiber",
  },
  {
    value: "blood_pressure_awareness",
    label: "Blood Pressure Awareness",
    hint: "Sodium, Potassium",
  },
  {
    value: "fitness_gym",
    label: "Fitness / Gym",
    hint: "Protein, Calories, Protein/100 kcal",
  },
  {
    value: "micronutrient_focus",
    label: "Micronutrient Focus",
    hint: "Iron, Calcium",
  },
];

const GOAL_OPTIONS: { value: ProfileGoalKey; label: string }[] = [
  { value: "balanced", label: "Balanced Nutrient Comparison" },
  { value: "higher_protein", label: "Higher Protein Focus" },
  { value: "higher_fiber_lower_sugar", label: "Higher Fiber / Lower Sugar Focus" },
  { value: "lower_sodium", label: "Lower Sodium Focus" },
  { value: "lower_calorie_density", label: "Lower Calorie Density" },
];

function computeLiveBmi(weightKg: number, heightCm: number) {
  if (!weightKg || !heightCm || weightKg <= 0 || heightCm <= 0) {
    return { bmi: 0, category: "Invalid", badgeStyle: "bg-slate-100 text-slate-600" };
  }
  const hM = heightCm / 100;
  const bmi = Math.round((weightKg / (hM * hM)) * 10) / 10;
  if (bmi < 18.5) {
    return {
      bmi,
      category: "Underweight",
      badgeStyle: "border-sky-200 bg-sky-50 text-sky-800",
    };
  }
  if (bmi < 25.0) {
    return {
      bmi,
      category: "Normal",
      badgeStyle: "border-emerald-200 bg-emerald-50 text-emerald-800",
    };
  }
  if (bmi < 30.0) {
    return {
      bmi,
      category: "Overweight",
      badgeStyle: "border-amber-200 bg-amber-50 text-amber-800",
    };
  }
  return {
    bmi,
    category: "Obese",
    badgeStyle: "border-rose-200 bg-rose-50 text-rose-800",
  };
}

function getAgeBracket(age: number): string {
  if (age <= 39) return "18–39";
  if (age <= 59) return "40–59";
  return "60+";
}

export function ContextFilter({ profile, onChange }: ContextFilterProps) {
  const bmiInfo = computeLiveBmi(profile.weight_kg, profile.height_cm);
  const ageBracket = getAgeBracket(profile.age);

  const toggleHealthContext = (key: HealthContextKey) => {
    if (key === "general_wellness") {
      onChange({ ...profile, health_contexts: ["general_wellness"] });
      return;
    }

    const currentWithoutGeneral = profile.health_contexts.filter(
      (c) => c !== "general_wellness"
    );
    const exists = currentWithoutGeneral.includes(key);
    const updated = exists
      ? currentWithoutGeneral.filter((c) => c !== key)
      : [...currentWithoutGeneral, key];

    onChange({
      ...profile,
      health_contexts: updated.length > 0 ? updated : ["general_wellness"],
    });
  };

  return (
    <div className="rounded-xl border border-purple-200 bg-gradient-to-br from-white to-purple-50/40 p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-purple-100 pb-2.5">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-purple-100 p-1.5 text-purple-700">
            <SlidersHorizontal className="h-4 w-4" />
          </div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-purple-950">
            CONTEXT FILTER
          </h3>
        </div>
        <span className="text-[11px] font-medium text-purple-700">
          Educational reference &amp; NHANES survey benchmarks — not clinical medical advice
        </span>
      </div>

      {/* Row 1: Age, Height, Weight + Live BMI Badge, Activity, Goal */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12">
        {/* Age */}
        <div className="lg:col-span-2">
          <label
            htmlFor="profile-age"
            className="mb-1 flex items-center justify-between text-xs font-medium text-slate-700"
          >
            <span className="inline-flex items-center gap-1">
              <User className="h-3.5 w-3.5 text-purple-600" />
              Age (yrs)
            </span>
            <span className="rounded bg-purple-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-purple-800">
              {ageBracket}
            </span>
          </label>
          <input
            id="profile-age"
            type="number"
            min={18}
            max={90}
            value={profile.age}
            onChange={(e) => {
              const val = Math.min(90, Math.max(18, Number(e.target.value) || 18));
              onChange({ ...profile, age: val });
            }}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono font-medium text-slate-900 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
          />
        </div>

        {/* Height & Weight + Auto BMI Badge */}
        <div className="sm:col-span-2 lg:col-span-5">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-700">
              Height (cm) &amp; Weight (kg)
            </span>
            <span
              data-testid="live-bmi-badge"
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${bmiInfo.badgeStyle}`}
            >
              BMI {bmiInfo.bmi.toFixed(1)} &bull; {bmiInfo.category}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="relative">
              <Ruler className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <input
                id="profile-height"
                aria-label="Height (cm)"
                type="number"
                min={100}
                max={250}
                step="0.5"
                value={profile.height_cm}
                onChange={(e) => {
                  const val = Math.max(50, Number(e.target.value) || 170);
                  onChange({ ...profile, height_cm: val });
                }}
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-8 pr-8 text-xs font-mono font-medium text-slate-900 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
              />
              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] text-slate-400">
                cm
              </span>
            </div>

            <div className="relative">
              <Scale className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <input
                id="profile-weight"
                aria-label="Weight (kg)"
                type="number"
                min={25}
                max={300}
                step="0.5"
                value={profile.weight_kg}
                onChange={(e) => {
                  const val = Math.max(20, Number(e.target.value) || 68);
                  onChange({ ...profile, weight_kg: val });
                }}
                className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-8 pr-8 text-xs font-mono font-medium text-slate-900 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
              />
              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] text-slate-400">
                kg
              </span>
            </div>
          </div>
        </div>

        {/* Activity Level */}
        <div className="lg:col-span-2">
          <label
            htmlFor="profile-activity"
            className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-700"
          >
            <Activity className="h-3.5 w-3.5 text-purple-600" />
            Activity Level
          </label>
          <select
            id="profile-activity"
            value={profile.activity_level}
            onChange={(e) =>
              onChange({
                ...profile,
                activity_level: e.target.value as ProfileActivityLevel,
              })
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-medium text-slate-800 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
          >
            {ACTIVITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Goal */}
        <div className="lg:col-span-3">
          <label
            htmlFor="profile-goal"
            className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-700"
          >
            <Target className="h-3.5 w-3.5 text-purple-600" />
            Goal
          </label>
          <select
            id="profile-goal"
            value={profile.goal}
            onChange={(e) =>
              onChange({
                ...profile,
                goal: e.target.value as ProfileGoalKey,
              })
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-xs font-medium text-slate-800 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20"
          >
            {GOAL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 2: Health / Wellness Context (Focus Area) multi-select chips */}
      <div className="mt-3 pt-2.5 border-t border-purple-100/80">
        <span className="mb-1.5 block text-xs font-medium text-slate-700">
          Health / Wellness Context (Focus Area — multi-select):
        </span>
        <div className="flex flex-wrap gap-1.5">
          {HEALTH_CONTEXT_OPTIONS.map((opt) => {
            const active = profile.health_contexts.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => toggleHealthContext(opt.value)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
                  active
                    ? "border-purple-600 bg-purple-600 text-white shadow-sm"
                    : "border-slate-200 bg-white text-slate-700 hover:border-purple-300 hover:text-purple-800"
                }`}
              >
                <span>{opt.label}</span>
                <span
                  className={`text-[10px] ${
                    active ? "text-purple-100" : "text-slate-400"
                  }`}
                >
                  ({opt.hint})
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
