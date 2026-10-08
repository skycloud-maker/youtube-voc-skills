"""Prompt payload builder for the future Golden120 semantic interpreter.

This module does not call any external LLM provider.  It only creates the
stable system instruction and user payload that a later OpenAI/LLM runner can
use to replace the current projection+heuristic path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


GOLDEN120_PROMPT_VERSION = "golden120-semantic-card-v4"

GOLDEN120_SYSTEM_PROMPT = """You are a Golden120 VoC semantic interpreter.
Return strict JSON only. Do not include markdown.

You are not creating new rules. Apply the project rules already established by
the Golden120 human review process.

Core principles:
1. Split by Atomic VoC, not by original comment row. Mixed sentiment, multiple
   products, multiple topics, inquiry plus praise/complaint, or unrelated targets
   must become separate units.
2. Use source context carefully: original comment first, then parent/reply,
   video title/source context only when the comment itself is insufficient.
3. Product VoC with unresolved CEJ is a CEJ calibration candidate, not automatically
   scope exclusion. Only non-product / low-value / negative-control cases become
   N/A or scope excluded.
4. TEE/S is about the product, feature, or CEJ experience. The act of writing a
   comment or asking a question is not Effort. A date or period is not Time unless
   it is part of the feature/topic experience.
5. Emotion requires explicit product/CEJ emotion. Simple neutral inquiries should
   not be forced into Emotion.
6. Root Cause maturity means how far the comment identifies problem and cause:
   N/A problem not identified, L1 problem exists but target unclear, L2 target
   identified but cause unknown, L3 target and cause both supported.
7. Watch/Agenda is not an approved rule. Use it as an observation flag only.
8. Return both a short feature/topic label for clustering and a sentence-style
   feature/topic description for subreason mapping.
9. Separate true N/A, scope exclusion, context missing, and engine/interpretation
   uncertainty. Do not hide uncertainty behind a generic "N/A".
10. Classify each unit's display tone as negative_concern, positive, inquiry,
   neutral, or excluded based on the unit meaning.
11. Prefer concrete product labels over broad groups. If the source context says
   robot vacuum, dishwasher, dryer, refrigerator, washer, etc., do not return a
   generic label such as appliance/home appliance.
12. Prefer concrete feature/topic labels. Do not return broad buckets such as
   cleaning/management/consumables when the text clearly mentions a feature
   like built-in station, auto-emptying, price policy, color option, climbing
   ability, inlet cover fit, or card discount.
13. Positive product/feature cues such as "대박", "만족", "좋다", "최고", "추천",
   or strong praise should not produce Emotion=N/A when the emotion is about
   the product, feature, or CEJ. Negative cues such as "비싸다", "불만", "우려",
   "걱정", "아쉽다", "무섭다", or price criticism must not produce a positive
   Emotion.
14. Feature praise is not automatically management. If the user is reacting to
   a feature before purchase/use, choose awareness/exploration. Choose usage
   only when direct use is shown, and management only when care, repair, A/S,
   cleaning, installation, or upkeep work is the user experience.
15. Every basis field must cite the concrete source evidence that caused the
   judgment. Prefer an exact Korean quote from the comment/parent context. If
   the evidence comes from video title/source context rather than the comment,
   say so explicitly. Do not write generic basis text such as "confirmed",
   "positive sentiment is observed", or "직접 신호 있음" without the source phrase.
16. Treat the semantic card JSONL as the canonical analysis draft. The dashboard
   should only render these fields; it should not invent product, CEJ, TEE/S,
   Root Cause, or summary values that are absent from the semantic rawdata.
17. Atomic splitting means appropriate splitting, not maximum splitting. Keep one
   coherent claim/intention/evaluation flow together. Split only when at least
   one of these is independently different: sentiment, target product/feature,
   CEJ stage, improvement point, or customer intent. Avoid over-splitting a
   single purchase-value argument such as "a feature was added and the price is
   still worth it".
18. For mixed source comments, each unit must carry its own strongest evidence.
   Do not reuse the first sentence as evidence for every field when a later
   phrase is the direct reason for the judgment.
19. Treat the analysis pipeline as Raw Comment -> ParentVoC -> AtomicVoC ->
   ReviewDecision -> DashboardAggregate. Preserve parent_voc_id, atomic_id,
   and atomic_index so one parent comment can produce multiple atomic units
   without losing lineage.
20. For explainability, each stage should expose label, reason, evidence,
   confidence, and status. Valid status values are normal, true_na,
   scope_excluded, context_missing, engine_missed, and review_required.
21. Evidence causality matters. Prefer evidence inside the atomic unit itself.
   If a judgment requires parent, video, source, script, or link context, keep
   that as context evidence rather than pretending it came from the atomic text.
22. Root Cause is improvement-task maturity: problem -> improvement target ->
   cause. L2 means an improvement target is visible even when the true cause is
   not known.

Output one JSON object with an `units` array. Each unit must include the 8-card
fields: product, feature_topic, atomic_voc, evidence_span, cej, tees, root_cause,
summary, plus routing metadata.
"""


GOLDEN120_DECISION_GUIDE: dict[str, Any] = {
    "atomic_unit_rule": {
        "unit": "One Atomic VoC, not one original comment row.",
        "split_when": [
            "positive and negative signals coexist",
            "multiple products, functions, or topics coexist",
            "inquiry and complaint/praise coexist",
            "product VoC and non-product/other-person behavior comment coexist",
        ],
        "do_not_split_when": [
            "one coherent claim/intention/evaluation flow is preserved",
            "price, feature, and value are part of one purchase-value argument",
            "clauses are supporting evidence for the same customer intent rather than independent VoCs",
        ],
        "split_quality": "Both under-splitting and over-splitting are quality issues.",
        "independence_test": [
            "independent sentiment",
            "independent product or feature target",
            "independent CEJ stage",
            "independent improvement point",
            "independent customer intent",
        ],
        "numbering_expectation": "A source VoC may become 1-1, 1-2, ... atomic units.",
    },
    "feature_topic_rule": {
        "label": "short clustering label such as 구매/가격/혜택 조건",
        "description": "sentence-style explanation for subreason mapping and human reading",
        "avoid_broad_defaults": [
            "Do not use cleaning/management/consumables unless that is directly supported.",
            "Use concrete feature labels first, for example built-in station / auto-emptying convenience.",
            "If the feature cannot be resolved, return context_missing or engine_missed rather than a misleading broad topic.",
        ],
    },
    "emotion_rule": {
        "positive_cues_require_emotion": ["대박", "만족", "좋다", "최고", "추천", "칭찬", "편하다"],
        "negative_cues_block_positive_emotion": ["비싸다", "불만", "우려", "걱정", "불안", "아쉽다", "무섭다", "실망"],
        "scope": "Emotion is included only when the feeling is about the product, feature, or CEJ experience.",
    },
    "cej_rule": {
        "feature_praise": "Do not route feature praise to management by default. Use awareness/exploration unless direct use or upkeep is shown.",
        "management_requires": "care, cleaning, repair, A/S, installation, maintenance, consumable replacement, or issue handling experience",
    },
    "na_status_rule": {
        "interpreted": "the axis was interpreted; N/A values are intentional",
        "true_na": "the source context truly has no signal for that axis",
        "scope_excluded": "not a product/experience VoC or low-value inquiry excluded from main denominator",
        "context_missing": "parent/video/source context is required before deciding",
        "engine_missed": "a signal appears present but the current engine may have missed it",
    },
    "root_cause_level_rule": {
        "N/A": "problem not identified; no concrete product/service issue",
        "L1": "problem exists but the target is unclear",
        "L2": "improvement target is identified, but cause is not identified",
        "L3": "problem and cause are both supported by source context",
        "note": "This is not a product defect verdict. It measures usefulness for improvement/root-cause work.",
    },
    "routing_rule": {
        "strategy_voc": "positive/negative product or experience signal useful for improvement/strategy",
        "inquiry_insight": "meaningful inquiry or information-access signal",
        "low_value_inquiry": "very short/simple inquiry with weak improvement signal",
        "watch_agenda": "case accumulation or unresolved policy boundary",
        "scope_excluded": "not in current analysis denominator",
    },
    "evidence_basis_rule": {
        "basis_contract": "Every non-N/A judgment basis should include exact evidence text and a short reason.",
        "preferred_format": "근거: \"exact source phrase\" / 판단: why this value was chosen",
        "source_order": ["comment text", "parent/reply context", "video title/source context", "video script/description if available"],
        "avoid": [
            "Do not say only that a signal was confirmed.",
            "Do not use dashboard display labels as evidence.",
            "Do not cite video/source context as if it appeared in the comment.",
        ],
    },
}


def build_golden120_semantic_prompt_payload(card: Mapping[str, Any]) -> dict[str, Any]:
    """Build the JSON payload for one candidate card.

    The payload intentionally includes the current projection result as
    `current_card_hint`, but instructs the model to treat it as a hint rather
    than ground truth.
    """

    context = card.get("semantic_context_payload", {})
    if not isinstance(context, Mapping):
        context = {}
    return {
        "prompt_version": GOLDEN120_PROMPT_VERSION,
        "task": "interpret_one_comment_or_candidate_unit_with_golden120_rules",
        "source_context": {
            "comment_text": str(context.get("comment_text", "") or card.get("atomic_voc", "")),
            "parent_comment_text": str(context.get("parent_comment_text", "") or ""),
            "video_title": str(context.get("video_title", "") or card.get("video_title", "")),
            "channel_title": str(context.get("channel_title", "") or ""),
            "source_product": str(context.get("source_product", "") or card.get("product_label", "")),
            "source_bucket": str(context.get("source_bucket", "") or ""),
            "comment_depth": str(context.get("comment_depth", "") or card.get("comment_depth", "")),
            "source_context_used": list(context.get("source_context_used", []) or card.get("source_context_used", [])),
        },
        "current_card_hint": {
            "product_label": card.get("product_label", ""),
            "product_detail": card.get("product_detail", ""),
            "feature_topic": card.get("feature_topic", ""),
            "atomic_voc": card.get("atomic_voc", ""),
            "evidence_span": card.get("evidence_span", ""),
            "cej_stage": card.get("cej_stage", ""),
            "tees": {
                "success": {"value": card.get("tees_success_value", ""), "basis": card.get("tees_success_basis", "")},
                "time": {"value": card.get("tees_time_value", ""), "basis": card.get("tees_time_basis", "")},
                "effort": {"value": card.get("tees_effort_value", ""), "basis": card.get("tees_effort_basis", "")},
                "emotion": {"value": card.get("tees_emotion_value", ""), "basis": card.get("tees_emotion_basis", "")},
            },
            "root_cause": {
                "level": card.get("root_problem_level", ""),
                "target": card.get("root_problem_target", ""),
                "category": card.get("root_cause_category", ""),
                "basis": card.get("root_cause_basis", ""),
            },
            "semantic_lane": card.get("semantic_lane", ""),
            "na_status": card.get("na_status", ""),
            "watch_agenda_flags": card.get("watch_agenda_flags", []),
        },
        "decision_guide": GOLDEN120_DECISION_GUIDE,
        "required_output_schema": {
            "units": [
                {
                    "product_label": "string",
                    "parent_voc_id": "stable original comment/parent VoC id",
                    "atomic_id": "stable id for this atomic unit",
                    "atomic_index": "1-based index within the parent VoC",
                    "atomic_split_reason": "why this is a separate atomic unit, or why it remained one",
                    "product_detail": "string",
                    "product_basis": "string",
                    "product_confidence": "high|medium|low",
                    "feature_topic_label": "string",
                    "feature_topic_description": "string",
                    "unit_title": "short Korean title for this atomic unit",
                    "atomic_voc": "exact or faithful unit text",
                    "evidence_span": "exact substring from source context when possible",
                    "cej_stage": "인지|탐색|결정|구매|배송|사용준비|사용|관리|교체|N/A",
                    "cej_basis": "string",
                    "cej_status": "interpreted|calibration_needed|context_needed|not_applicable",
                    "tees_success_value": "string or N/A",
                    "tees_success_basis": "string",
                    "tees_time_value": "string or N/A",
                    "tees_time_basis": "string",
                    "tees_effort_value": "string or N/A",
                    "tees_effort_basis": "string",
                    "tees_emotion_value": "string or N/A",
                    "tees_emotion_basis": "string",
                    "root_problem_level": "N/A|L1|L2|L3",
                    "root_cause_problem": "problem statement or N/A",
                    "root_problem_target": "string",
                    "root_cause_cause": "cause statement if supported, otherwise N/A",
                    "root_cause_category": "string",
                    "root_cause_basis": "string",
                    "atomic_evidence": "exact quote from the atomic unit text",
                    "context_evidence": "parent/video/source/script/link evidence if used",
                    "evidence_scope": "atomic_internal|parent_comment_context|external_context|missing",
                    "scope_status": "in_scope|scope_excluded|watch_candidate|context_needed",
                    "na_status": "interpreted|true_na|scope_excluded|context_missing|engine_missed|not_applicable",
                    "stage_status": {
                        "parent": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "atomic": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "topic": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "cej": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "tees_success": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "tees_time": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "tees_effort": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "tees_emotion": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "root_cause": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                        "summary": "normal|true_na|scope_excluded|context_missing|engine_missed|review_required",
                    },
                    "polarity_label": "negative_concern|positive|inquiry|neutral|excluded",
                    "semantic_lane": "strategy_voc|inquiry_insight|low_value_inquiry|watch_agenda|review_queue|scope_excluded|observation",
                    "semantic_lane_reason": "string",
                    "watch_agenda_flags": ["string"],
                    "summary": "human-readable Korean VoC interpretation",
                    "confidence_notes": ["string"],
                    "needs_human_review": "boolean",
                }
            ]
        },
        "basis_format_requirement": {
            "non_na_basis": "Use `근거: \"...\" / 판단: ...` whenever possible.",
            "context_basis": "If using parent/video/source context, name that source explicitly.",
            "generic_basis_is_invalid": "Generic text such as 'confirmed' or 'signal observed' is insufficient without exact evidence.",
        },
    }


def build_golden120_semantic_user_prompt(card: Mapping[str, Any]) -> str:
    payload = build_golden120_semantic_prompt_payload(card)
    return (
        "Interpret this comment/candidate unit using the Golden120 rules and return JSON only.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}"
    )
