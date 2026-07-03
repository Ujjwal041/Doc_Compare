# IntelliSynth

**AI-driven plan benefit synthesis module of the IntelliOne platform.**

IntelliSynth reads PBM (Pharmacy Benefit Manager) plan documents, extracts all benefit rules using Claude AI, builds a structured Knowledge Graph, and layers a Temporal Graph on top — so every rule knows exactly when it was valid. The resulting graph is queried by IntelliCERT to produce date-accurate claim validation verdicts.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
  - [Step 1 — Document Parsing](#step-1--document-parsing)
  - [Step 2 — LLM Entity Extraction](#step-2--llm-entity-extraction)
  - [Step 3 — Knowledge Graph](#step-3--knowledge-graph)
  - [Step 4 — Temporal Graph](#step-4--temporal-graph)
  - [Step 5 — Date-Accurate Querying](#step-5--date-accurate-querying)
- [Temporal Graph — How Dates Work](#temporal-graph--how-dates-work)
- [Document Types](#document-types)
- [Node Types](#node-types)
- [Edge Types](#edge-types)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [API Key](#api-key)
- [Output Files](#output-files)
- [Integration with IntelliCERT](#integration-with-intellicert)
- [Tech Stack](#tech-stack)

---

## What It Does

IntelliSynth automates what was previously a manual process: reading 100+ plan documents, understanding which rules apply, and knowing which version of a rule was active on any given date.

**Before IntelliSynth:**
```
QA analyst reads Base Plan SPD (80 pages)
→ Reads Amendment (20 pages)
→ Reads Specialty Rider (15 pages)
→ Manually figures out which rule applies for a claim from March
→ Hours of work per plan × 100+ plans = weeks
```

**After IntelliSynth:**
```
Upload 3 documents → Graph built in seconds
Query: get_rule_as_of("Metformin", "2024-02-15")
→ Returns: Tier-1, $50, effective Jan 1 (Base SPD)
```

---

## Project Structure

```
intellisynth/
│
├── run_test.py              # Main test runner — runs full pipeline
├── show_timestamps.py       # Timestamp viewer — shows all node dates
├── synth_pipeline.py        # Orchestrator — coordinates all steps
│
├── graph/
│   ├── knowledge_graph.py   # Step 3: builds nodes + edges (no time)
│   └── temporal_graph.py    # Step 4: adds effective dates, handles amendments
│
├── utils/
│   ├── parser.py            # Step 1: extracts text + tables from .docx
│   └── extractor.py         # Step 2: Claude LLM entity extraction + mock
│
└── output/
    ├── extracted_base_spd.json         # Raw LLM extraction output
    ├── extracted_amendment.json        # Amendment changes extracted
    ├── extracted_rider.json            # Rider rules extracted
    └── PLAN-TECHCORP-2024_temporal_graph.json  # Saved graph
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 0 — Input Documents                              │
│  Base Plan SPD (Jan 1) · Amendment #1 (Jul 1)           │
│  Specialty Rider (Mar 1)                                │
└──────────────────────┬──────────────────────────────────┘
                       │ python-docx
┌──────────────────────▼──────────────────────────────────┐
│  LAYER 1 — Document Parser (utils/parser.py)            │
│  Sections · Tables · Effective date extraction          │
└──────────────────────┬──────────────────────────────────┘
                       │ raw text + tables
┌──────────────────────▼──────────────────────────────────┐
│  LAYER 2 — LLM Entity Extraction (utils/extractor.py)   │
│  Claude Sonnet → structured JSON rules                  │
│  Mock fallback when no API key                          │
└──────────────────────┬──────────────────────────────────┘
                       │ structured rules dict
┌──────────────────────▼──────────────────────────────────┐
│  LAYER 3 — Knowledge Graph (graph/knowledge_graph.py)   │
│  NetworkX DiGraph · Nodes + Edges · No time yet         │
│  CopayRule · PAREquirement · StepTherapyRule            │
│  Exclusion · CoverageLimit · SpecialCoverage            │
└──────────────────────┬──────────────────────────────────┘
                       │ stamp effective dates
┌──────────────────────▼──────────────────────────────────┐
│  LAYER 4 — Temporal Graph (graph/temporal_graph.py)     │
│  effective_from · effective_to · superseded             │
│  AMENDED_BY edges · EXTENDED_BY edges                   │
│  Amendment: close old node → create new → connect       │
└──────────────────────┬──────────────────────────────────┘
                       │ get_rule_as_of(drug, date)
┌──────────────────────▼──────────────────────────────────┐
│  LAYER 5 — IntelliCERT (LangGraph pipeline)             │
│  PRE date query · POST date query · Verdict             │
└─────────────────────────────────────────────────────────┘
```

---

## How It Works

### Step 1 — Document Parsing

`utils/parser.py` reads `.docx` files using `python-docx` and returns structured output:

```python
from utils.parser import parse_docx, extract_effective_date

parsed = parse_docx("Base_Plan_SPD_TECHCORP_2024.docx")

# Returns:
{
    "full_text": "TECHCORP HEALTH BENEFITS...",
    "sections": {
        "SECTION 4 — DRUG TIER STRUCTURE": "Tier-1 generics...",
        "SECTION 6 — PRIOR AUTHORIZATION": "PA required for...",
    },
    "tables": [
        {
            "headers": ["Drug Name", "Tier", "Copay", "PA Required"],
            "rows": [["Metformin 500mg", "Tier-1", "$50", "No"], ...]
        }
    ],
    "metadata": {"total_paragraphs": 65, "total_sections": 19}
}
```

### Step 2 — LLM Entity Extraction

`utils/extractor.py` sends parsed text to Claude and gets structured rules back as JSON.

**With API key** → Claude Sonnet extracts rules from real document text.

**Without API key** → Mock extraction returns realistic pre-defined rules (used for testing).

```python
rules = extract_rules_from_document(
    plan_id        = "PLAN-TECHCORP-2024",
    doc_type       = "BASE_SPD",
    full_text      = parsed["full_text"],
    effective_date = "2024-01-01",
    tables         = parsed["tables"],
)

# Returns:
{
    "copay_rules": [
        {"rule_id": "COPAY_METFORMIN_500", "drug_name": "Metformin 500mg",
         "tier": "Tier-1", "copay_amount": 50, "section_reference": "Section 4.2"}
    ],
    "pa_requirements": [
        {"rule_id": "PA_INSULIN_GLARGINE", "drug_name": "Insulin Glargine",
         "pa_required": True, "pa_criteria": "Diabetes diagnosis required",
         "reject_code": "75"}
    ],
    "amendment_changes": [  # Only for AMENDMENT doc_type
        {"change_id": "AMD1_METFORMIN_TIER", "drug_name": "Metformin",
         "change_type": "tier_change",
         "old_value": "Tier-1, $50", "new_value": "Tier-2, $200",
         "section_amended": "4.2", "effective_date": "2024-07-01"}
    ]
}
```

### Step 3 — Knowledge Graph

`graph/knowledge_graph.py` builds a NetworkX `DiGraph`. Nodes represent rules. Edges represent relationships. No time metadata at this stage — just *what* the rules are.

```python
from graph.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph("PLAN-TECHCORP-2024")
kg.ingest_extracted_rules(rules)

# Graph state after Base SPD:
# 22 nodes (1 plan + 21 rules)
# 21 edges (plan → each rule)

# Query:
metformin_rules = kg.get_drug_rules("Metformin")
# Returns all nodes where drug_name contains "Metformin"
```

**Node structure (CopayRule example):**
```
node_id   : "PLAN-TECHCORP-2024_COPAY_METFORMIN_500"
node_type : "CopayRule"
label     : "Metformin 500mg → Tier-1 → $50"
drug_name : "Metformin 500mg"
tier      : "Tier-1"
copay_amount : 50
section_ref  : "Section 4.2"
```

### Step 4 — Temporal Graph

`graph/temporal_graph.py` extends `KnowledgeGraph` with time metadata and amendment processing.

**Stamping Base SPD nodes:**
```python
tg.stamp_base_spd_nodes("2024-01-01", "Base_Plan_SPD.docx")

# Every node now has:
# effective_from = "2024-01-01"
# effective_to   = None          (open ended)
# superseded     = False
# version        = 1
# source_doc     = "Base_Plan_SPD.docx"
```

**Processing an Amendment:**
```python
tg.process_amendment(amendment_rules, "2024-07-01", "Amendment_1.docx")

# For Metformin change:
# 1. OLD node → effective_to="2024-06-30", superseded=True
# 2. NEW node → effective_from="2024-07-01", version=2
# 3. Edge: OLD ──[AMENDED_BY]──► NEW
```

**Stamping Rider nodes:**
```python
tg.stamp_rider_nodes("2024-03-01", "Specialty_Rider.docx")

# Rider nodes get:
# effective_from = "2024-03-01"
# edge type changed to EXTENDED_BY (not AMENDED_BY)
```

### Step 5 — Date-Accurate Querying

```python
def get_rule_as_of(drug_name, query_date):
    """
    Returns rules active on query_date.
    
    A rule is active if ALL three are true:
    1. effective_from <= query_date
    2. effective_to is None OR query_date <= effective_to
    3. superseded == False  (when node is open-ended)
    """
```

---

## Temporal Graph — How Dates Work

### Timeline Visualization

```
Jan 1          Mar 1          Jun 30  Jul 1          Dec 31
  |              |              |       |              |
  |──────────────────────────────|       |              |
  Metformin v1  Tier-1  $50             |              |
  ❌ SUPERSEDED (effective_to=Jun30)     |              |
                                         |──────────────|
                                         Metformin v2  Tier-2  $200
                                         ✅ ACTIVE (effective_to=None)

  |──────────────────────────────────────────────────────|
  Atorvastatin  Tier-1  $50                              
  ✅ ACTIVE — untouched by amendment

              |───────────────────────────────────────────|
              Herceptin $100  (Specialty Rider)
              ✅ ACTIVE from Mar 1

  |──────────────────|
  PA_Insulin_v1       |───────────────────────────────────|
  PA Always Required  PA Waived if HbA1c > 9  (v2)
  ❌ SUPERSEDED       ✅ ACTIVE from Jul 1
```

### Query Results by Date

| Drug | Query Date | Returns | Source |
|------|-----------|---------|--------|
| Metformin | Feb 15 | Tier-1, $50 | Base SPD |
| Metformin | Jul 10 | Tier-2, $200 | Amendment #1 |
| Herceptin | Feb 15 | No rule | Before rider effective date |
| Herceptin | Mar 15 | $100 flat | Specialty Rider |
| Insulin Glargine PA | Feb 15 | PA Required | Base SPD |
| Insulin Glargine PA | Jul 10 | PA Waived if HbA1c>9 | Amendment #1 |
| Humira step therapy | Jun 15 | DMARD failure required | Base SPD |
| Humira step therapy | Jul 10 | Amjevita biosimilar first | Amendment #1 |

### Why This Matters for Certification

```
Without temporal graph:
  PRE claim: Feb 15 → $50 copay
  POST cert: Jul 10 → validates against current rule ($200)
  System: "$50 was wrong!" → INVALID ❌ (FALSE verdict)

With temporal graph:
  PRE claim: get_rule("Metformin", "Feb 15") → $50 ✅ correct for Feb
  POST cert: get_rule("Metformin", "Jul 10") → $200 ✅ correct for Jul
  System: "Both values correct for their dates" → VALID ✅
```

---

## Document Types

| Document | Role | Effective Date | Graph Action |
|----------|------|---------------|--------------|
| Base Plan SPD | Foundation — all base benefit rules | Jan 1 (plan year start) | Creates all base nodes, stamps with `effective_from` |
| Specialty Rider | Additive — new coverage on top of base | Mar 1 (rider start) | Adds new nodes with `EXTENDED_BY` edges |
| Amendment | Override — changes specific base rules | Jul 1 (amendment date) | Closes old nodes, creates new nodes, adds `AMENDED_BY` edges |

---

## Node Types

| Node Type | What It Stores | Key Fields |
|-----------|---------------|------------|
| `Plan` | Plan identity | `plan_id` |
| `CopayRule` | Drug tier + copay amount | `drug_name`, `tier`, `copay_amount`, `days_supply` |
| `PAREquirement` | Prior authorization rules | `pa_required`, `pa_criteria`, `pa_waiver_condition`, `reject_code` |
| `StepTherapyRule` | Step therapy requirements | `target_drug`, `required_first_step`, `trial_duration_days`, `reject_code` |
| `Exclusion` | Excluded drug classes | `drug_or_class`, `examples`, `reject_code`, `exception_available` |
| `CoverageLimit` | Days supply / quantity limits | `limit_type`, `max_value`, `applies_to` |
| `SpecialCoverage` | Rider special coverage | `drug_class`, `special_copay`, `step_therapy_waived`, `quantity_limit_waived` |

**All nodes also carry temporal metadata:**

| Field | Type | Description |
|-------|------|-------------|
| `effective_from` | `str` (YYYY-MM-DD) | Date rule became active |
| `effective_to` | `str` or `None` | Date rule was superseded (None = still active) |
| `superseded` | `bool` | Whether this node was replaced by an amendment |
| `version` | `int` | Version number (1 = original, 2+ = amended) |
| `source_doc` | `str` | Which document this rule came from |

---

## Edge Types

| Edge | From | To | Meaning |
|------|------|----|---------|
| `HAS_COPAY_RULE` | Plan | CopayRule | Plan defines this copay |
| `REQUIRES_PA` | Plan | PAREquirement | Plan requires PA for this drug |
| `HAS_STEP_THERAPY` | Plan | StepTherapyRule | Plan has step therapy requirement |
| `EXCLUDES` | Plan | Exclusion | Plan excludes this drug/class |
| `HAS_LIMIT` | Plan | CoverageLimit | Plan has this coverage limit |
| `EXTENDS_COVERAGE` | Plan | SpecialCoverage | Rider extends coverage (additive) |
| `AMENDED_BY` | Old node | New node | Old rule was replaced by amendment |

---

## Quick Start

### Install dependencies

```bash
pip install networkx python-docx anthropic
```

### Run the full pipeline

```bash
cd intellisynth
python3 run_test.py
```

This runs:
1. Parses all 3 dummy documents (Base SPD, Amendment, Specialty Rider)
2. Extracts rules (via Claude or mock fallback)
3. Builds Knowledge Graph
4. Adds Temporal Layer
5. Runs 8 temporal query test cases
6. Saves graph to `output/`

### View timestamps

```bash
python3 show_timestamps.py
```

Shows every node with its `effective_from`, `effective_to`, and status, plus all AMENDED_BY and EXTENDED_BY edges, plus a live temporal query demo.

### Use in your own code

```python
from synth_pipeline import IntelliSynthPipeline

synth = IntelliSynthPipeline("PLAN-TECHCORP-2024", output_dir="output")

synth.ingest_base_spd("Base_Plan_SPD.docx", effective_date="2024-01-01")
synth.ingest_specialty_rider("Specialty_Rider.docx", effective_date="2024-03-01")
synth.ingest_amendment("Amendment_1.docx", effective_date="2024-07-01")

tg = synth.get_temporal_graph()

# Query — what was the copay for Metformin on Feb 15?
rules = tg.get_rule_as_of("Metformin", "2024-02-15")
# → CopayRule: Tier-1, $50 (Base SPD, Jan 1 – Jun 30)

# Full amendment chain for a drug
chain = tg.get_amendment_chain("Metformin")
# → v1 (Base SPD, Jan–Jun, superseded)
# → v2 (Amendment #1, Jul+, active)
```

---

## Running Tests

```bash
python3 run_test.py
```

**Test cases:**

| # | Drug | Date | Expected | Tests |
|---|------|------|----------|-------|
| 1 | Metformin | Feb 15 | Tier-1, $50 | Base SPD rule returned for pre-amendment date |
| 2 | Metformin | Jul 10 | Tier-2, $200 | Amendment rule returned for post-amendment date |
| 3 | Insulin PA | Feb 15 | PA Required | Original PA requirement active before amendment |
| 4 | Insulin PA | Jul 10 | PA Waived (HbA1c) | Amended PA rule active after amendment |
| 5 | Herceptin | Mar 15 | $100 flat | Rider rule active after rider effective date |
| 6 | Humira | Jun 15 | PA + DMARD step | Original step therapy active before amendment |
| 7 | Adalimumab | Jul 10 | Amjevita step | Amended step therapy active after amendment |
| 8 | Metformin | Dec 31 | Tier-2, $200 | Amended rule still active at year end |

---

## API Key

IntelliSynth works in two modes:

**Without API key (testing/dev):**
```bash
python3 run_test.py
# → Uses mock extraction
# → All graph + temporal logic runs normally
# → 7/8 tests pass
```

**With API key (production):**
```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
python3 run_test.py
# → Claude Sonnet extracts real rules from actual documents
# → More accurate for diverse document formats
```

Only the `extract_rules_from_document()` function in `utils/extractor.py` requires the API key. All graph building, temporal processing, and querying are fully local with no external dependencies.

---

## Output Files

| File | Description |
|------|-------------|
| `output/extracted_base_spd.json` | Raw structured rules extracted from Base SPD |
| `output/extracted_amendment.json` | Amendment changes extracted (old/new values) |
| `output/extracted_rider.json` | Rider special coverage rules extracted |
| `output/PLAN-TECHCORP-2024_temporal_graph.json` | Full serialized temporal graph (NetworkX node-link format) |

The graph JSON can be loaded back at any time:
```python
tg = TemporalGraph("PLAN-TECHCORP-2024")
tg.load("output/PLAN-TECHCORP-2024_temporal_graph.json")
rules = tg.get_rule_as_of("Metformin", "2024-07-10")
```

---

## Integration with IntelliCERT

IntelliCERT's `validate_with_rag()` node calls IntelliSynth's temporal graph directly:

```python
# In IntelliCERT LangGraph node:
from intellisynth.graph.temporal_graph import TemporalGraph

tg = TemporalGraph("PLAN-TECHCORP-2024")
tg.load("output/PLAN-TECHCORP-2024_temporal_graph.json")

# For a Paid-Paid mismatch on Metformin:
pre_rule  = tg.get_rule_as_of("Metformin", claim.pre_claim_date)
post_rule = tg.get_rule_as_of("Metformin", claim.post_claim_date)

# Verdict logic:
if pre_copay == pre_rule[0]["copay_amount"]:
    if post_copay == post_rule[0]["copay_amount"]:
        verdict = "Valid"
        reason  = f"Amendment #1 changed Metformin Tier-1→Tier-2 on Jul 1. " \
                  f"Both PRE ${pre_copay} and POST ${post_copay} are correct."
    else:
        verdict = "Invalid"
else:
    verdict = "Invalid"
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Document parsing | `python-docx` | Native .docx support, table extraction |
| Entity extraction | `anthropic` (Claude Sonnet) | Handles varied document formats, extracts structured JSON |
| Knowledge Graph | `networkx.DiGraph` | Lightweight, pure Python, node/edge queries |
| Temporal layer | Custom on NetworkX | Adds 5 temporal fields + amendment processing |
| Graph persistence | JSON (node-link format) | Standard NetworkX serialization, human-readable |
| Testing | Pure Python | No framework needed — deterministic graph queries |

---

## Key Design Decisions

**Why NetworkX and not Neo4j?**
NetworkX runs in-process with no infrastructure. For 100+ plans × ~30 nodes each (~3000 nodes total), in-memory is faster and simpler. Neo4j makes sense when plans scale to millions of nodes or when cross-plan graph queries (e.g. "find all plans where Metformin is Tier-2") become a core feature.

**Why not overwrite nodes on amendment?**
Overwriting loses the PRE claim history. A claim processed in February needs February's rules to validate correctly — if those rules are gone, IntelliCERT produces false Invalid verdicts. Closing old nodes and creating versioned new ones preserves full audit history at zero extra query cost.

**Why a mock extraction fallback?**
The entire pipeline — parsing, graph building, temporal logic, querying — can run and be tested without an LLM call. This means graph architecture can be developed and validated independently of API availability or cost, and CI/CD pipelines can run tests without credentials.

---

*IntelliSynth is part of IntelliOne — Intelligent Claims Validation Platform.*
*Modules: IntelliSynth · Intelli360 · IntelliCERT*
