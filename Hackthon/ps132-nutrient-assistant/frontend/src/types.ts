export type AgeGroup = "all_adults" | "18-39" | "40-59" | "60+";
export type ProfileActivityLevel = "low" | "moderate" | "active";
export type HealthContextKey =
  | "general_wellness"
  | "blood_sugar_awareness"
  | "blood_pressure_awareness"
  | "fitness_gym"
  | "micronutrient_focus";
export type ProfileGoalKey =
  | "balanced"
  | "higher_protein"
  | "higher_fiber_lower_sugar"
  | "lower_sodium"
  | "lower_calorie_density";

export type FocusLens =
  | "balanced"
  | "protein_energy"
  | "carb_fiber"
  | "sodium_potassium"
  | "iron_calcium";

export interface UserProfile {
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ProfileActivityLevel;
  health_contexts: HealthContextKey[];
  goal: ProfileGoalKey;
}

export interface VisionPrediction {
  name: string;
  confidence: number;
}

export interface IdentifyImageResponse {
  provider: string;
  predictions: VisionPrediction[];
  note: string;
}

export interface FoodRecord {
  food_id: string;
  name: string;
  aliases: string;
  state: string;
  source_name: string;
  source_url: string;
  energy_kcal: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fiber_g: number | null;
  sugar_g: number | null;
  fat_g: number | null;
  sodium_mg: number | null;
  potassium_mg: number | null;
  iron_mg: number | null;
  calcium_mg: number | null;
}

export interface ComparedFoodSummary {
  food_id: string;
  name: string;
  state: string;
  aliases: string[];
  portion_g: number;
  source_name: string;
  source_url: string;
  scaled_nutrients: Record<string, number | null>;
  per_100g_record: FoodRecord;
  match_method?: string;
  similarity_score?: number;
}

export interface NutrientComparisonRow {
  key: string;
  label: string;
  unit: string;
  is_focused: boolean;
  is_priority?: boolean;
  food_a_value: number | null;
  food_a_display: string;
  food_b_value: number | null;
  food_b_display: string;
  diff_a_minus_b: number | null;
  diff_display: string;
  pct_diff_vs_b: number | null;
  pct_diff_display: string;
  higher_in: "A" | "B" | "equal" | "N/A";
  nhanes_median: number | null;
  nhanes_median_display: string;
  food_a_pct_nhanes_median: number | null;
  food_b_pct_nhanes_median: number | null;
  pct_nhanes_median: {
    food_a: number | null;
    food_b: number | null;
  };
}

export interface NhanesSurveyStatistics {
  sample_size: number;
  median_bmi: number | null;
  median_systolic_bp_mmhg: number | null;
  median_diastolic_bp_mmhg: number | null;
  pct_self_reported_diabetes: number | null;
  note: string;
}

export interface NhanesContext {
  age_group: string;
  activity_level: string;
  bmi_range: string;
  focus_lens: FocusLens;
  focus_lens_label: string;
  focus_keys: string[];
  sample_size: number | null;
  cohort_medians: Record<string, number | null>;
  survey_statistics: NhanesSurveyStatistics;
  data_origin: string;
  source_name: string;
  source_url: string;
}

export interface NhanesBenchmarkItem {
  age_group: string;
  activity_level: string;
  bmi_range: string;
  sample_size: number;
  medians: Record<string, number | null>;
  survey_statistics: NhanesSurveyStatistics;
  data_origin: string;
  source_name: string;
  source_url: string;
}

export interface NutrientTag {
  label: string;
  category: string;
  metric_text: string;
  is_priority: boolean;
}

export interface ProfileSummary {
  age: number;
  age_group: string;
  height_cm: number;
  weight_kg: number;
  bmi: number;
  bmi_category: string;
  bmi_range: string;
  activity_level: string;
  activity_label: string;
  nhanes_activity_bucket: string;
  health_contexts: string[];
  health_context_labels: string[];
  goal: string;
  goal_label: string;
  summary_line: string;
}

export interface ModelAssessment {
  food_a_score: number;
  food_b_score: number;
  food_a_tier: string;
  food_b_tier: string;
  food_a_strengths: string[];
  food_b_strengths: string[];
  recommended_choice: "food_a" | "food_b" | "balanced_tie";
  verdict_badge: string;
  verdict_title: string;
  verdict_summary: string;
}

export interface FinalReport {
  title: string;
  generated_at: string;
  markdown: string;
}

export interface RulesAnalysis {
  profile_summary: ProfileSummary;
  priority_nutrients: { key: string; label: string; unit: string }[];
  focus_lens: FocusLens;
  focus_lens_label: string;
  derived_metrics: {
    food_a: { protein_per_100kcal: number | null; kcal_per_100g: number | null };
    food_b: { protein_per_100kcal: number | null; kcal_per_100g: number | null };
  };
  food_tags: {
    food_a: NutrientTag[];
    food_b: NutrientTag[];
  };
  model_assessment?: ModelAssessment;
  suggestions?: string[];
  final_report?: FinalReport;
  comparison_rows: NutrientComparisonRow[];
  nhanes_benchmarks: NhanesContext | null;
}

export interface GuardrailPayload {
  blocked: boolean;
  reason_category: string | null;
  matched_signals: string[];
  message: string;
  suggested_comparison: string | null;
  suggested_lens: FocusLens | null;
  suggested_lens_label: string | null;
  disclaimer: string;
}

export interface CompareResponse {
  status: "ok" | "blocked";
  guardrail: GuardrailPayload;
  comparison?: {
    food_a: ComparedFoodSummary;
    food_b: ComparedFoodSummary;
    rows: NutrientComparisonRow[];
    focus_lens: FocusLens;
    focus_lens_label: string;
    nhanes_context: NhanesContext | null;
  };
  rules_analysis?: RulesAnalysis;
  explanation?: {
    text: string;
    profile_context_summary?: string;
    bullet_points?: string[];
    provider: string;
  };
  meta?: {
    parser: string;
    user_profile?: ProfileSummary;
    layers_executed: string[];
  };
}
