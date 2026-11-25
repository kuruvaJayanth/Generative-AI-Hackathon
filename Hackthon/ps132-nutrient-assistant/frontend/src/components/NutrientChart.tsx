import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ComparedFoodSummary, FocusLens, NutrientComparisonRow } from "../types";

interface NutrientChartProps {
  foodA: ComparedFoodSummary;
  foodB: ComparedFoodSummary;
  rows: NutrientComparisonRow[];
  focusLens?: FocusLens;
}

type ChartGroup = "macros" | "electrolytes" | "iron" | "energy";

export function NutrientChart({
  foodA,
  foodB,
  rows,
  focusLens = "balanced",
}: NutrientChartProps) {
  const [group, setGroup] = useState<ChartGroup>("macros");

  useEffect(() => {
    if (focusLens === "sodium_potassium") setGroup("electrolytes");
    else if (focusLens === "iron_calcium") setGroup("iron");
    else if (focusLens === "protein_energy") setGroup("macros");
    else if (focusLens === "carb_fiber") setGroup("macros");
  }, [focusLens]);

  const filteredKeys: Record<ChartGroup, string[]> = {
    macros: ["protein_g", "carbs_g", "fiber_g", "sugar_g", "fat_g"],
    electrolytes: ["sodium_mg", "potassium_mg", "calcium_mg"],
    iron: ["iron_mg"],
    energy: ["energy_kcal"],
  };

  const chartData = rows
    .filter((r) => filteredKeys[group].includes(r.key))
    .map((r) => ({
      name: `${r.label} (${r.unit})`,
      [foodA.name]: r.food_a_value ?? 0,
      [foodB.name]: r.food_b_value ?? 0,
    }));

  const labelA = `${foodA.name} (${foodA.portion_g}g)`;
  const labelB = `${foodB.name} (${foodB.portion_g}g)`;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Visual Nutrient Profile
          </h3>
          <p className="text-xs text-slate-500">
            Portion-scaled comparison chart grouped by unit scale
          </p>
        </div>

        <div className="inline-flex flex-wrap rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs font-medium">
          {(
            [
              { id: "macros", label: "Macros (g)" },
              { id: "electrolytes", label: "Na / K / Ca (mg)" },
              { id: "iron", label: "Iron (mg)" },
              { id: "energy", label: "Energy (kcal)" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setGroup(tab.id)}
              className={`rounded-md px-2.5 py-1 transition ${
                group === tab.id
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: "#475569" }}
              axisLine={{ stroke: "#cbd5e1" }}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#475569" }}
              axisLine={{ stroke: "#cbd5e1" }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: "12px",
                borderColor: "#cbd5e1",
                fontSize: "12px",
              }}
            />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
            <Bar
              dataKey={foodA.name}
              name={labelA}
              fill="#2563eb"
              radius={[6, 6, 0, 0]}
              maxBarSize={48}
            />
            <Bar
              dataKey={foodB.name}
              name={labelB}
              fill="#10b981"
              radius={[6, 6, 0, 0]}
              maxBarSize={48}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
