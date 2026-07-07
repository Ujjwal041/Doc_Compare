Part 1 — What to Store from Each PDF
For every PDF, you store 4 things at different levels:

LEVEL 1 — Document Metadata (once per PDF)
─────────────────────────────────────────
{
  "source_pdf"     : "Base_Plan_SPD.pdf",
  "doc_type"       : "BASE_SPD",          ← BASE_SPD | AMENDMENT | RIDER
  "plan_id"        : "PLAN-TECHCORP-2024",
  "total_pages"    : 180,
  "effective_date" : "2024-01-01",     ← the ONE date that governs this doc
  "uploaded_at"    : "2026-07-04T...",
  "job_id"         : "1d225bec"
}

LEVEL 2 — Extracted Rules (structured, from LLM)
─────────────────────────────────────────
{
  "copay_rules"        : [...],   ← drug, tier, amount, section_ref
  "pa_requirements"    : [...],   ← drug, criteria, reject_code
  "step_therapy_rules" : [...],
  "exclusions"         : [...],
  "coverage_limits"    : [...],
  "special_coverages"  : [...],   ← only for RIDER
  "amendment_changes"  : [...]    ← only for AMENDMENT
}

LEVEL 3 — Date Occurrences (all dates, classified)
─────────────────────────────────────────
[
  {
    "date_iso"    : "2024-07-01",
    "page_number" : 134,
    "section"     : "Amendment to Section 4.2",
    "context"     : "...hereby amended effective July 1...",
    "date_type"   : "AMENDMENT_EFFECTIVE_DATE",
    "source_pdf"  : "Base_Plan_SPD.pdf"
  },
  ...
]

LEVEL 4 — Raw Text Chunks (for vector search, optional)
─────────────────────────────────────────
ChromaDB chunks with metadata:
  {plan_id, source_pdf, page_number, section}


Part 2 — How Everything Correlates

The correlation happens through three keys that link everything:

        plan_id  ──────────  ties all 3 PDFs to ONE plan
        source_pdf ────────  ties every rule/date to its PDF
        section_ref ───────  ties amendment changes to base rules

Here's the full correlation chain:     
   

Base_Plan_SPD.pdf
    │
    │ (parse + extract)
    ▼
Rule: Metformin, Tier-1, $50, section_ref="4.2"
    │
    │ (KG build)
    ▼
Node: Metformin_v1
    source_doc  = "Base_Plan_SPD.pdf"
    section_ref = "Section 4.2"
    │
    │ (TG stamp using doc's effective_date)
    ▼
Node: Metformin_v1 + [effective_from: 2024-01-01]
    │
    │ Amendment_1.pdf arrives —
    │ it says: "Section 4.2 is amended"
    │            ↑
    │   THIS is the correlation key!
    │   section_amended="4.2" matches section_ref="4.2"
    │   + drug_name="Metformin" matches node's drug_name
    ▼
System finds Metformin_v1 → closes it [effective_to: Jun 30]
Creates Metformin_v2 [effective_from: Jul 1]
    source_doc = "Amendment_1.pdf"     ← different PDF!
Edge: Metformin_v1 ──[AMENDED_BY]──► Metformin_v2


The three-way match that connects an amendment to a base rule:

Same plan_id (both docs belong to PLAN-TECHCORP-2024)
Same drug_name (Metformin ↔ Metformin)
Same section (Amendment says "Section 4.2" → base node has section_ref "4.2")

Part 3 — What Happens When Multiple PDFs Upload

Job: 1d225bec
User uploads 3 PDFs (any order)
        │
        ▼
STEP 0 — Classify each PDF's type
─────────────────────────────────
For each PDF, detect doc_type from content:
  "Summary Plan Description" in cover  → BASE_SPD
  "Amendment #" + "hereby amended"     → AMENDMENT  
  "Rider" + "addendum"                 → SPECIALTY_RIDER
        │
        ▼
STEP 1 — Force processing ORDER (regardless of upload order)
─────────────────────────────────
  1st: BASE_SPD        (creates foundation nodes)
  2nd: SPECIALTY_RIDER (adds EXTENDED_BY nodes)
  3rd: AMENDMENT       (modifies existing nodes)

  Why? Amendment needs base nodes to exist,
  otherwise there's nothing to close/chain.
        │
        ▼
STEP 2 — Extract per-PDF (parallel OK)
─────────────────────────────────
  Each PDF → parse → dates scan → LLM extract
  Every output tagged with source_pdf
        │
        ▼
STEP 3 — Build ONE unified graph
─────────────────────────────────
  All 3 PDFs feed the SAME TemporalGraph object.
  Not 3 graphs — ONE graph, 3 source documents.

  Base SPD:  21 nodes [Jan 1]  source: Base_Plan_SPD.pdf
  + Rider:    4 nodes [Mar 1]  source: Specialty_Rider.pdf
  + Amend:   3 closed, 3 new [Jul 1]  source: Amendment_1.pdf
  
  Final: 28 nodes, one graph, full history
        │
        ▼
STEP 4 — Persist
─────────────────────────────────
  NetworkX JSON: PLAN-TECHCORP-2024_temporal_graph.json
  Neo4j: nodes + AMENDED_BY + EXTENDED_BY relationships

  Key insight — conflicts between PDFs are resolved by the edge type:

Part 4 — The Final Storage Picture

After 3 PDFs processed, you have:

📁 File storage
   ├── Base_Plan_SPD.pdf          (original, kept for audit)
   ├── Amendment_1.pdf
   └── Specialty_Rider.pdf

📁 Extraction outputs (JSON)
   ├── extracted_base_spd.json     (rules + dates from PDF 1)
   ├── extracted_amendment.json    (changes from PDF 2)
   └── extracted_rider.json        (coverages from PDF 3)

🕸️ ONE Temporal Graph (2 stores)
   ├── NetworkX JSON  → fast in-memory queries
   └── Neo4j          → persistent + visual + Cypher

📊 ChromaDB (optional)
   └── text chunks with {source_pdf, page} metadata
       for "what does the document say" vector queries