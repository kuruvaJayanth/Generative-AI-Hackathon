import { ChangeEvent, DragEvent, useState } from "react";
import {
  ArrowRightLeft,
  Camera,
  Check,
  FileText,
  ImagePlus,
  Loader2,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import {
  IdentifyImageResponse,
  UserProfile,
  VisionPrediction,
} from "../types";
import { ContextFilter } from "./ContextFilter";

interface InputPanelProps {
  loading: boolean;
  userProfile: UserProfile;
  onUserProfileChange: (next: UserProfile) => void;
  onCompareText: (query: string) => Promise<void>;
  onCompareMixed: (payload: {
    food_a: string;
    grams_a: number;
    food_b: string;
    grams_b: number;
  }) => Promise<void>;
}

interface SlotState {
  mode: "image" | "text";
  textName: string;
  grams: string;
  previewUrl: string | null;
  fileName: string | null;
  identifying: boolean;
  identifyError: string | null;
  provider: string | null;
  note: string | null;
  predictions: VisionPrediction[];
}

const DEMO_CHIPS: { label: string; query: string; isGuardrail?: boolean }[] = [
  {
    label: "150g cooked quinoa vs 100g rolled oats",
    query: "Compare 150g cooked quinoa vs 100g rolled oats",
  },
  {
    label: "ragi vs moong dal",
    query: "ragi vs moong dal",
  },
  {
    label: "100g paneer vs 100g boiled egg",
    query: "100g paneer vs 100g boiled egg",
  },
  {
    label: "Guardrail demo: diabetes breakfast",
    query: "I have diabetes, what should I eat for breakfast?",
    isGuardrail: true,
  },
  {
    label: "Guardrail demo: BP & sodium limit",
    query: "I am a BP patient with BMI 29, how much sodium can I eat?",
    isGuardrail: true,
  },
];

function createInitialSlot(mode: "image" | "text", defaultText = ""): SlotState {
  return {
    mode,
    textName: defaultText,
    grams: "100",
    previewUrl: null,
    fileName: null,
    identifying: false,
    identifyError: null,
    provider: null,
    note: null,
    predictions: [],
  };
}

export function InputPanel({
  loading,
  userProfile,
  onUserProfileChange,
  onCompareText,
  onCompareMixed,
}: InputPanelProps) {
  const [textQuery, setTextQuery] = useState(
    "Compare 150g cooked quinoa vs 100g rolled oats"
  );
  const [slotA, setSlotA] = useState<SlotState>(() =>
    createInitialSlot("image", "")
  );
  const [slotB, setSlotB] = useState<SlotState>(() =>
    createInitialSlot("text", "rolled oats")
  );
  const [autoCompareImage, setAutoCompareImage] = useState(true);
  const [dragOverSlot, setDragOverSlot] = useState<"A" | "B" | null>(null);

  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textQuery.trim() || loading) return;
    await onCompareText(textQuery.trim());
  };

  const handleChipClick = async (query: string) => {
    setTextQuery(query);
    if (!loading) {
      await onCompareText(query);
    }
  };

  const updateSlot = (
    slot: "A" | "B",
    updater: (prev: SlotState) => SlotState
  ) => {
    if (slot === "A") setSlotA(updater);
    else setSlotB(updater);
  };

  const triggerSlotCompare = async (
    nextNameA: string,
    nextGramsA: string,
    nextNameB: string,
    nextGramsB: string
  ) => {
    if (!nextNameA.trim() || !nextNameB.trim()) return;
    await onCompareMixed({
      food_a: nextNameA.trim(),
      grams_a: Math.max(1, Number(nextGramsA) || 100),
      food_b: nextNameB.trim(),
      grams_b: Math.max(1, Number(nextGramsB) || 100),
    });
  };

  const handleIdentifyFile = async (slot: "A" | "B", file: File) => {
    const previewUrl = URL.createObjectURL(file);
    updateSlot(slot, (prev) => ({
      ...prev,
      mode: "image",
      previewUrl,
      fileName: file.name,
      identifying: true,
      identifyError: null,
      predictions: [],
      provider: null,
      note: null,
    }));

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/identify-image", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "Failed to identify food image.");
      }
      const data: IdentifyImageResponse = await res.json();
      const topPrediction = data.predictions[0]?.name || "";
      updateSlot(slot, (prev) => ({
        ...prev,
        identifying: false,
        provider: data.provider,
        note: data.note,
        predictions: data.predictions,
        textName: topPrediction,
      }));

      // Automatically run full comparison + report once Vision AI identifies the food
      if (autoCompareImage && topPrediction) {
        const nameA = slot === "A" ? topPrediction : slotA.textName;
        const gramsA = slotA.grams;
        const nameB = slot === "B" ? topPrediction : slotB.textName;
        const gramsB = slotB.grams;
        if (nameA.trim() && nameB.trim()) {
          await triggerSlotCompare(nameA, gramsA, nameB, gramsB);
        }
      }
    } catch (err) {
      updateSlot(slot, (prev) => ({
        ...prev,
        identifying: false,
        identifyError:
          err instanceof Error ? err.message : "Image identification error.",
      }));
    }
  };

  const handleSelectPrediction = async (slot: "A" | "B", predName: string) => {
    updateSlot(slot, (prev) => ({
      ...prev,
      textName: predName,
    }));
    if (autoCompareImage) {
      const nameA = slot === "A" ? predName : slotA.textName;
      const nameB = slot === "B" ? predName : slotB.textName;
      if (nameA.trim() && nameB.trim()) {
        await triggerSlotCompare(nameA, slotA.grams, nameB, slotB.grams);
      }
    }
  };

  const handleFileInput = (
    slot: "A" | "B",
    e: ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (file) {
      void handleIdentifyFile(slot, file);
    }
    e.target.value = "";
  };

  const handleDrop = (slot: "A" | "B", e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragOverSlot(null);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      void handleIdentifyFile(slot, file);
    }
  };

  const clearSlotImage = (slot: "A" | "B") => {
    updateSlot(slot, (prev) => ({
      ...prev,
      previewUrl: null,
      fileName: null,
      predictions: [],
      provider: null,
      note: null,
      identifyError: null,
    }));
  };

  const handleMixedSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slotA.textName.trim() || !slotB.textName.trim() || loading) return;
    await triggerSlotCompare(
      slotA.textName,
      slotA.grams,
      slotB.textName,
      slotB.grams
    );
  };

  const renderSlot = (slotKey: "A" | "B", state: SlotState) => {
    const isA = slotKey === "A";
    const badgeClasses = isA
      ? "bg-blue-100 text-blue-800"
      : "bg-emerald-100 text-emerald-800";

    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${badgeClasses}`}
            >
              Food {slotKey}
            </span>
            <span className="text-xs font-medium text-slate-600">
              {state.mode === "image" ? "Upload Food Image" : "Enter Food Name"}
            </span>
          </div>

          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs">
            <button
              type="button"
              onClick={() =>
                updateSlot(slotKey, (prev) => ({ ...prev, mode: "image" }))
              }
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-medium transition ${
                state.mode === "image"
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Camera className="h-3 w-3" />
              Image
            </button>
            <button
              type="button"
              onClick={() =>
                updateSlot(slotKey, (prev) => ({ ...prev, mode: "text" }))
              }
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 font-medium transition ${
                state.mode === "text"
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <FileText className="h-3 w-3" />
              Text
            </button>
          </div>
        </div>

        {state.mode === "image" && (
          <div className="mb-3 space-y-2.5">
            {!state.previewUrl ? (
              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOverSlot(slotKey);
                }}
                onDragLeave={() => setDragOverSlot(null)}
                onDrop={(e) => handleDrop(slotKey, e)}
                className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-5 text-center transition ${
                  dragOverSlot === slotKey
                    ? "border-blue-500 bg-blue-50/70"
                    : "border-slate-300 bg-white hover:border-blue-400 hover:bg-slate-50"
                }`}
              >
                <ImagePlus className="mb-1.5 h-6 w-6 text-slate-400" />
                <span className="text-xs font-medium text-slate-700">
                  Drag &amp; drop any Food {slotKey} photo or{" "}
                  <span className="text-blue-600 underline">browse</span>
                </span>
                <span className="mt-0.5 text-[11px] text-slate-400">
                  CLIP / Gemini Vision recognizes any dish, fruit, grain, or snack
                </span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleFileInput(slotKey, e)}
                  className="hidden"
                />
              </label>
            ) : (
              <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-2.5">
                <img
                  src={state.previewUrl}
                  alt={`Uploaded Food ${slotKey}`}
                  className="h-16 w-16 shrink-0 rounded-lg object-cover"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-xs font-medium text-slate-800">
                      {state.fileName}
                    </p>
                    <button
                      type="button"
                      onClick={() => clearSlotImage(slotKey)}
                      aria-label={`Remove Food ${slotKey} image`}
                      className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {state.identifying && (
                    <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-blue-600">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Recognizing food in image...
                    </p>
                  )}

                  {state.identifyError && (
                    <p className="mt-1 text-xs text-rose-600">
                      {state.identifyError}
                    </p>
                  )}

                  {state.provider && (
                    <p className="mt-1 text-[11px] text-slate-500">
                      Recognized via{" "}
                      <span className="font-mono font-medium text-slate-700">
                        {state.provider}
                      </span>
                    </p>
                  )}
                </div>
              </div>
            )}

            {state.predictions.length > 0 && (
              <div className="space-y-1.5 rounded-xl border border-blue-100 bg-white p-2.5">
                <p className="text-[11px] font-medium text-slate-600">
                  Top-3 Vision Predictions (click to compare or edit below):
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {state.predictions.map((pred) => {
                    const selected =
                      state.textName.trim().toLowerCase() ===
                      pred.name.toLowerCase();
                    return (
                      <button
                        key={pred.name}
                        type="button"
                        onClick={() => void handleSelectPrediction(slotKey, pred.name)}
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                          selected
                            ? "border-blue-600 bg-blue-600 text-white"
                            : "border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-300"
                        }`}
                      >
                        {selected && <Check className="h-3 w-3" />}
                        {pred.name}
                        <span className="opacity-75">
                          ({Math.round(pred.confidence * 100)}%)
                        </span>
                      </button>
                    );
                  })}
                </div>
                {state.note && (
                  <p className="text-[11px] text-slate-500">{state.note}</p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-3 gap-2">
          <div className="col-span-2">
            <label className="mb-1 block text-[11px] font-medium text-slate-600">
              {state.mode === "image"
                ? `Confirmed / Edited Food ${slotKey}`
                : `Food ${slotKey} Name`}
            </label>
            <input
              type="text"
              value={state.textName}
              onChange={(e) =>
                updateSlot(slotKey, (prev) => ({
                  ...prev,
                  textName: e.target.value,
                }))
              }
              placeholder={
                isA ? "e.g., pizza, dosa, or quinoa" : "e.g., rolled oats"
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-600">
              Portion (g)
            </label>
            <input
              type="number"
              min={1}
              step="any"
              value={state.grams}
              onChange={(e) =>
                updateSlot(slotKey, (prev) => ({
                  ...prev,
                  grams: e.target.value,
                }))
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
        </div>
      </div>
    );
  };

  return (
    <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Layer 1: Dual Input Panel &amp; User Context Profile
          </h2>
          <p className="text-xs text-slate-500">
            Compare via free text, upload 1–2 food photos, or mix image + text
          </p>
        </div>
      </div>

      {/* Mode 1: Free-Text Comparison */}
      <form onSubmit={handleTextSubmit} className="space-y-3">
        <label
          htmlFor="text-comparison-input"
          className="block text-xs font-semibold uppercase tracking-wide text-slate-600"
        >
          Enter Food Name (Text)
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              id="text-comparison-input"
              type="text"
              value={textQuery}
              onChange={(e) => setTextQuery(e.target.value)}
              placeholder='e.g., "Compare 150g cooked quinoa vs 100g rolled oats" or "ragi vs moong dal"'
              className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !textQuery.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRightLeft className="h-4 w-4" />
            )}
            Compare / Analyze
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500">
            <Sparkles className="h-3.5 w-3.5 text-blue-500" />
            Quick-fill demos:
          </span>
          {DEMO_CHIPS.map((chip) => (
            <button
              key={chip.query}
              type="button"
              onClick={() => void handleChipClick(chip.query)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                chip.isGuardrail
                  ? "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
                  : "border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </form>

      <div className="relative py-1">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-slate-200" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-white px-3 text-xs font-medium text-slate-400">
            OR UPLOAD FOOD IMAGE / MIX MODES (IMAGE + TEXT)
          </span>
        </div>
      </div>

      {/* Mode 2: Dual Slot Image Upload & Mixed Mode */}
      <form onSubmit={handleMixedSubmit} className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          {renderSlot("A", slotA)}
          {renderSlot("B", slotB)}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={autoCompareImage}
              onChange={(e) => setAutoCompareImage(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            Auto-compare &amp; generate report as soon as food image is recognized
          </label>

          <button
            type="submit"
            disabled={
              loading || !slotA.textName.trim() || !slotB.textName.trim()
            }
            className="inline-flex items-center gap-2 rounded-xl border border-slate-900 bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRightLeft className="h-4 w-4" />
            )}
            Compare Food A vs Food B
          </button>
        </div>
      </form>

      {/* Full User Profile Context Filter */}
      <ContextFilter profile={userProfile} onChange={onUserProfileChange} />
    </section>
  );
}
