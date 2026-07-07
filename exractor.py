
import os
import json


def extract_rules_from_document(
    plan_id: str,
    doc_type: str,
    full_text: str,
    effective_date: str,
    tables: list,
) -> dict:

    client = _get_client()

    if client is None:
        print("  ⚠️  No API key — using mock extraction for testing")
        return _mock_extract(plan_id, doc_type, effective_date)

    table_summary = ""
    for i, t in enumerate(tables[:6]):
        table_summary += f"\nTable {i+1} headers: {t['headers']}\n"
        for row in t["rows"][:5]:
            table_summary += f"  Row: {row}\n"

    system_prompt = """You are a PBM document parser.
Extract structured benefit rules from plan documents.
Return ONLY valid JSON — no markdown, no explanation, no preamble."""

    user_prompt = f"""
Extract ALL benefit rules from this {doc_type} document.
Plan ID: {plan_id}
Effective Date: {effective_date}

DOCUMENT TEXT (first 8000 chars):
{full_text[:8000]}

TABLE DATA:
{table_summary}

Return JSON with this EXACT structure:
{{
  "plan_id": "{plan_id}",
  "doc_type": "{doc_type}",
  "effective_date": "{effective_date}",
  "copay_rules": [
    {{
      "rule_id": "COPAY_METFORMIN_T1",
      "drug_name": "Metformin",
      "drug_ndc": null,
      "tier": "Tier-1",
      "copay_amount": 50,
      "copay_unit": "per_fill",
      "days_supply": 30,
      "drug_type": "generic",
      "condition": null,
      "section_reference": "Section 4.2"
    }}
  ],
  "pa_requirements": [
    {{
      "rule_id": "PA_INSULIN_GLARGINE",
      "drug_name": "Insulin Glargine",
      "drug_ndc": null,
      "pa_required": true,
      "pa_criteria": "Diagnosis of Type 1 or Type 2 Diabetes",
      "pa_duration_months": 12,
      "pa_waiver_condition": null,
      "reject_code": "75",
      "section_reference": "Section 6.1"
    }}
  ],
  "step_therapy_rules": [
    {{
      "rule_id": "STEP_HUMIRA",
      "target_drug": "Adalimumab (Humira)",
      "required_first_step": "DMARD failure required",
      "trial_duration_days": 60,
      "documentation_needed": "Physician attestation",
      "reject_code": "76",
      "section_reference": "Section 8.3"
    }}
  ],
  "exclusions": [
    {{
      "rule_id": "EXCL_COSMETIC",
      "drug_or_class": "Cosmetic medications",
      "examples": ["Minoxidil", "Tretinoin"],
      "reject_code": "70",
      "exception_available": false,
      "section_reference": "Section 7.1"
    }}
  ],
  "coverage_limits": [
    {{
      "rule_id": "LIMIT_DAYS_SUPPLY",
      "limit_type": "days_supply",
      "max_value": 30,
      "applies_to": "all retail drugs",
      "reject_code": "76",
      "section_reference": "Section 4.3"
    }}
  ],
  "special_coverages": [
    {{
      "rule_id": "ONCOLOGY_FLAT",
      "coverage_type": "oncology_rider",
      "drug_class": "Oncology drugs",
      "special_copay": 100,
      "pa_required": true,
      "step_therapy_waived": true,
      "quantity_limit_waived": true,
      "eligibility_criteria": "confirmed cancer diagnosis",
      "section_reference": "Part A"
    }}
  ],
  "amendment_changes": [
    {{
      "change_id": "AMD1_METFORMIN",
      "section_amended": "4.2",
      "drug_name": "Metformin",
      "change_type": "tier_change",
      "old_value": "Tier-1, $50",
      "new_value": "Tier-2, $200",
      "reason": "Brand reclassification",
      "effective_date": "{effective_date}"
    }}
  ]
}}
Only populate amendment_changes for AMENDMENT doc_type.
Only populate special_coverages for SPECIALTY_RIDER doc_type.
Extract EVERY rule you find — be exhaustive.
"""

    try:
        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 4000,
            system     = system_prompt,
            messages   = [{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except Exception as e:
        print(f"  ⚠️  LLM extraction failed: {e} — using mock")
        return _mock_extract(plan_id, doc_type, effective_date)


def _mock_extract(plan_id: str, doc_type: str, effective_date: str) -> dict:
    """
    Realistic mock extraction for testing without API key.
    Mirrors exactly what Claude would extract from the dummy documents.
    """
    base = {
        "plan_id": plan_id,
        "doc_type": doc_type,
        "effective_date": effective_date,
        "copay_rules": [],
        "pa_requirements": [],
        "step_therapy_rules": [],
        "exclusions": [],
        "coverage_limits": [],
        "special_coverages": [],
        "amendment_changes": [],
        "_mock": True,
    }

    if doc_type == "BASE_SPD":
        base["copay_rules"] = [
            {"rule_id":"COPAY_METFORMIN_500","drug_name":"Metformin 500mg","drug_ndc":"00071-0155-23","tier":"Tier-1","copay_amount":50,"copay_unit":"per_fill","days_supply":30,"drug_type":"generic","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_METFORMIN_1000","drug_name":"Metformin 1000mg","drug_ndc":None,"tier":"Tier-1","copay_amount":50,"copay_unit":"per_fill","days_supply":30,"drug_type":"generic","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_ATORVASTATIN","drug_name":"Atorvastatin","drug_ndc":None,"tier":"Tier-1","copay_amount":50,"copay_unit":"per_fill","days_supply":30,"drug_type":"generic","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_LISINOPRIL","drug_name":"Lisinopril","drug_ndc":None,"tier":"Tier-1","copay_amount":50,"copay_unit":"per_fill","days_supply":30,"drug_type":"generic","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_INSULIN_GLARGINE","drug_name":"Insulin Glargine","drug_ndc":"00088-5021-99","tier":"Tier-2","copay_amount":200,"copay_unit":"per_fill","days_supply":30,"drug_type":"brand","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_INSULIN_ASPART","drug_name":"Insulin Aspart","drug_ndc":"00169-7501-11","tier":"Tier-2","copay_amount":200,"copay_unit":"per_fill","days_supply":30,"drug_type":"brand","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_LIPITOR","drug_name":"Lipitor","drug_ndc":None,"tier":"Tier-2","copay_amount":200,"copay_unit":"per_fill","days_supply":30,"drug_type":"brand","condition":None,"section_reference":"Section 4.2"},
            {"rule_id":"COPAY_HUMIRA","drug_name":"Adalimumab (Humira)","drug_ndc":"00074-9355-02","tier":"Tier-4","copay_amount":500,"copay_unit":"per_fill_plus_coinsurance","days_supply":30,"drug_type":"specialty","condition":"20% coinsurance after copay","section_reference":"Section 4.2"},
            {"rule_id":"COPAY_ELIQUIS","drug_name":"Apixaban (Eliquis)","drug_ndc":None,"tier":"Tier-3","copay_amount":500,"copay_unit":"per_fill","days_supply":30,"drug_type":"brand","condition":None,"section_reference":"Section 4.2"},
        ]
        base["pa_requirements"] = [
            {"rule_id":"PA_INSULIN_GLARGINE","drug_name":"Insulin Glargine","drug_ndc":"00088-5021-99","pa_required":True,"pa_criteria":"Diagnosis of Type 1 or Type 2 Diabetes confirmed by prescribing physician. Prior trial of basal insulin required.","pa_duration_months":12,"pa_waiver_condition":None,"reject_code":"75","section_reference":"Section 6.1"},
            {"rule_id":"PA_INSULIN_ASPART","drug_name":"Insulin Aspart","drug_ndc":"00169-7501-11","pa_required":True,"pa_criteria":"Diagnosis of Type 1 Diabetes OR Type 2 with HbA1c > 8 documented within 6 months.","pa_duration_months":12,"pa_waiver_condition":None,"reject_code":"75","section_reference":"Section 6.1"},
            {"rule_id":"PA_HUMIRA","drug_name":"Adalimumab (Humira)","drug_ndc":"00074-9355-02","pa_required":True,"pa_criteria":"Confirmed diagnosis of RA, Psoriatic Arthritis, or Crohn's Disease. Must document failure of at least one DMARD.","pa_duration_months":6,"pa_waiver_condition":None,"reject_code":"75","section_reference":"Section 6.1"},
        ]
        base["step_therapy_rules"] = [
            {"rule_id":"STEP_ELIQUIS","target_drug":"Apixaban (Eliquis)","required_first_step":"Warfarin (generic) — minimum 30 days trial","trial_duration_days":30,"documentation_needed":"Physician attestation of Warfarin failure or contraindication","reject_code":"76","section_reference":"Section 8.2"},
            {"rule_id":"STEP_HUMIRA","target_drug":"Adalimumab (Humira)","required_first_step":"Failure of at least one conventional DMARD (Methotrexate or Sulfasalazine)","trial_duration_days":90,"documentation_needed":"Documentation of DMARD failure","reject_code":"76","section_reference":"Section 8.3"},
        ]
        base["exclusions"] = [
            {"rule_id":"EXCL_COSMETIC","drug_or_class":"Cosmetic medications","examples":["Minoxidil topical","Tretinoin cream"],"reject_code":"70","exception_available":False,"section_reference":"Section 7.1"},
            {"rule_id":"EXCL_WEIGHT_LOSS","drug_or_class":"Weight loss drugs (non-prescription)","examples":["Orlistat OTC","weight loss supplements"],"reject_code":"70","exception_available":False,"section_reference":"Section 7.1"},
            {"rule_id":"EXCL_ERECTILE","drug_or_class":"Erectile dysfunction drugs","examples":["Sildenafil (for ED)","Tadalafil (for ED)"],"reject_code":"70","exception_available":True,"section_reference":"Section 7.1"},
            {"rule_id":"EXCL_NON_FORMULARY","drug_or_class":"Non-formulary drugs","examples":[],"reject_code":"70","exception_available":True,"section_reference":"Section 7.1"},
        ]
        base["coverage_limits"] = [
            {"rule_id":"LIMIT_DAYS_RETAIL","limit_type":"days_supply_retail","max_value":30,"applies_to":"All retail pharmacy drugs","reject_code":"76","section_reference":"Section 4.3"},
            {"rule_id":"LIMIT_FILLS_QTR","limit_type":"fills_per_quarter","max_value":3,"applies_to":"All retail pharmacy drugs","reject_code":"76","section_reference":"Section 4.3"},
            {"rule_id":"LIMIT_OOP","limit_type":"out_of_pocket_annual","max_value":3000,"applies_to":"Individual member","reject_code":None,"section_reference":"Section 4.4"},
        ]

    elif doc_type == "SPECIALTY_RIDER":
        base["special_coverages"] = [
            {"rule_id":"ONCOLOGY_FLAT_COPAY","coverage_type":"oncology_rider","drug_class":"Oncology drugs","special_copay":100,"pa_required":True,"step_therapy_waived":True,"quantity_limit_waived":True,"eligibility_criteria":"Confirmed active cancer diagnosis ICD-10 C00-D49","section_reference":"Part A.2"},
            {"rule_id":"ONCOLOGY_HERCEPTIN","coverage_type":"oncology_rider","drug_class":"Trastuzumab (Herceptin)","special_copay":100,"pa_required":True,"step_therapy_waived":True,"quantity_limit_waived":True,"eligibility_criteria":"HER2-positive breast cancer diagnosis","section_reference":"Part A.2"},
            {"rule_id":"BIOLOGIC_COSENTYX","coverage_type":"biologic_rider","drug_class":"Secukinumab (Cosentyx)","special_copay":300,"pa_required":True,"step_therapy_waived":False,"quantity_limit_waived":False,"eligibility_criteria":"Psoriasis, PsA, or AS diagnosis","section_reference":"Part B.2"},
            {"rule_id":"BIOLOGIC_STELARA","coverage_type":"biologic_rider","drug_class":"Ustekinumab (Stelara)","special_copay":300,"pa_required":True,"step_therapy_waived":False,"quantity_limit_waived":False,"eligibility_criteria":"Crohn's disease or Psoriasis diagnosis","section_reference":"Part B.2"},
        ]

    elif doc_type == "AMENDMENT":
        base["amendment_changes"] = [
            {
                "change_id"       : "AMD1_METFORMIN_TIER",
                "section_amended" : "4.2",
                "drug_name"       : "Metformin",
                "change_type"     : "tier_change",
                "old_value"       : "Tier-1, $50",
                "new_value"       : "Tier-2, $200",
                "reason"          : "Brand reclassification by P&T Committee — extended-release brand formulations preferred",
                "effective_date"  : effective_date,
            },
            {
                "change_id"       : "AMD1_INSULIN_PA",
                "section_amended" : "6.1",
                "drug_name"       : "Insulin Glargine",
                "change_type"     : "pa_change",
                "old_value"       : "PA always required for all members",
                "new_value"       : "PA waived if HbA1c > 9.0 documented within last 6 months. PA still required for HbA1c <= 9.0",
                "reason"          : "Expedite access for severe uncontrolled diabetics",
                "effective_date"  : effective_date,
            },
            {
                "change_id"       : "AMD1_HUMIRA_STEP",
                "section_amended" : "8.3",
                "drug_name"       : "Adalimumab (Humira)",
                "change_type"     : "step_therapy_change",
                "old_value"       : "PA required + DMARD failure documentation",
                "new_value"       : "PA required + must first try Adalimumab-atto (Amjevita) biosimilar for minimum 60 days",
                "reason"          : "Biosimilar first policy to reduce specialty drug costs",
                "effective_date"  : effective_date,
            },
        ]

    return base