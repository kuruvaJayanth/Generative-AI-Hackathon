# PS 132: Food Nutrient Comparison Assistant

A complete, runnable 5-step full-stack prototype for factual, portion-scaled food nutrient comparisons combining Vision AI, User Profile & BMI Processing, Hybrid RAG retrieval, CDC NHANES 2017–2018 population benchmarks, a deterministic Nutrition Reference Rules Engine, and pre-retrieval clinical advice guardrails.

## 5-Step Architecture & Data Flow

1. **User Profile & Input Layer (`frontend/src/components/InputPanel.tsx`, `ContextFilter.tsx`)**
   - **Enter Food Name (Text)**: Free-text comparisons (e.g., `"Compare 150g cooked quinoa vs 100g rolled oats"`, `"ragi vs moong dal"`) with quick-fill demo chips.
   - **Upload Food Image & Mixed Mode**: Drag-and-drop or file picker for 1–2 food photos (`POST /api/identify-image`) with top-3 editable predictions and seamless mixing (image + text).
   - **Context Filter**: Age (`18–90`), Height (cm), Weight (kg) with live auto-calculated BMI & category badge, Activity Level, multi-select Health / Wellness Context chips (`General Wellness`, `Blood Sugar Awareness`, `Blood Pressure Awareness`, `Fitness / Gym`, `Micronutrient Focus`), and Goal.
2. **Profile Processing (`backend/profile_processor.py`)**
   - Deterministically computes BMI (`weight_kg / (height_cm / 100)^2`), maps Age → NHANES bracket (`18-39`, `40-59`, `60+`), Activity → NHANES `PAQ_J` bucket, and builds ordered `priority_nutrients`.
3. **Vision AI & Hybrid RAG Retrieval (`backend/vision.py`, `backend/rag_store.py`, `backend/nhanes_benchmarks.py`)**
   - MobileNetV2 local weights (`models/food_classifier.pth`) with Gemini Vision (`gemini-2.5-flash`) fallback.
   - SQLite + ChromaDB hybrid store over USDA FoodData Central and ICMR-NIN IFCT 2017 records, plus CDC NHANES 2017–2018 `.XPT` cohort benchmarks (`nhanes_benchmarks`).
4. **Nutrition Reference Rules Engine (`backend/math_engine.py`, `backend/rules_engine.py`)**
   - Scales nutrients deterministically (`grams / 100.0`), computes `A - B` diffs, `% vs B`, `% of NHANES observed median`, `protein_per_100kcal`, prioritizes relevant table rows, and generates factual Nutrient Profile Tags (`Higher Protein`, `Higher Dietary Fiber`, `Lower Sodium`, `Rich in Iron`, etc.).
5. **Tailored, Source-Linked Non-Clinical Output (`backend/guardrail.py`, `backend/llm_service.py`)**
   - Pre-retrieval clinical guardrail blocks medical/therapeutic requests and offers a one-click redirect to an objective lens comparison.
   - Generates a 1-sentence Profile Context Summary + 3–4 objective bullet points grounded strictly in `rules_analysis` JSON, alongside clickable source links (USDA FDC, ICMR-NIN IFCT 2017, CDC NHANES 2017–2018), raw JSON drawer, read-only Observed Survey Statistics (`DIQ_J` & `BPX_J`), and persistent informational disclaimer.

## Setup & Run Instructions

### 1. Environment Variables (Optional for Offline Demo)
```bash
cp .env.example .env
# Optionally populate GEMINI_API_KEY and USDA_FDC_API_KEY
```

### 2. Backend Setup & Run
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

#### Optional: Process Real CDC NHANES 2017–2018 `.XPT` Files
Place `DEMO_J.XPT`, `BMX_J.XPT`, `PAQ_J.XPT`, `DR1TOT_J.XPT`, `DIQ_J.XPT`, and `BPX_J.XPT` into `data/nhanes/` and run:
```bash
cd backend
python nhanes_benchmarks.py --nhanes-dir ../data/nhanes
```

### 3. Frontend Setup & Run
```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in your browser.

### 4. Run Automated Tests
```bash
pytest tests/test_pipeline.py tests/test_nhanes_feature.py tests/test_profile_rules.py -v
```
