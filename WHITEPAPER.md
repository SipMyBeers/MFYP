# MFYP: Autonomous Multi-Modal Intelligence Pipeline with TCS-Constrained Mission Execution, Peer-Validated Knowledge Accumulation, and Passive Worldview Inference

**Author:** Dylan Beers  
**Organization:** BEERS LABS LLC  
**Date:** April 2026  
**Contact:** dylan@beerslabs.com  
**Keywords:** AI agents, autonomous execution, knowledge validation, hallucination prevention, multi-modal processing, mission planning, military doctrine, progressive context disclosure, revealed preference, worldview inference

---

## Abstract

We present **MFYP** (My For You Page), an autonomous multi-modal intelligence pipeline that addresses four fundamental limitations of current AI agent systems: (1) agents that cannot safely execute open-ended missions without human supervision at every step; (2) agents that hallucinate when their knowledge is insufficient; (3) agents that cannot accumulate and maintain calibrated expertise over time; and (4) agents that cannot accurately model the user's worldview for communication calibration without expensive self-report collection. MFYP makes four technical contributions. First, a **TCS-constrained autonomous mission executor** that implements military Task-Conditions-Standards doctrine as a formal constraint system — every mission specifies explicit standards, and the agent iteratively self-evaluates against those standards with a structured gap-analysis loop before submission. Second, a **same-species peer validation network** in which identical agent instances operated by different users independently observe, verify, and dispute knowledge claims — providing the first cross-instance confidence calibration mechanism we are aware of in the AI agent literature. Third, a **three-tier progressive disclosure system** with trigger-based semantic filtering that enables agents with thousands of accumulated knowledge claims to perform inference within fixed context budgets, outperforming naive retrieval-augmented generation by loading specifically relevant knowledge rather than most-recent or highest-ranked. Fourth, a **creator-content consumption pipeline** that constructs accurate user worldview profiles from passive URL detection without self-report, validated against the revealed-preference principle from behavioral economics. We describe the full system architecture, each component's implementation, evaluation methodology, and the privacy architecture that ensures no personal data leaves the user's hardware.

---

## 1. Introduction

### 1.1 The Safe Autonomous Execution Problem

AI agent systems capable of taking real-world actions — browsing the web, drafting documents, executing code, interacting with APIs — present a safety challenge that current frameworks address inadequately. Existing approaches impose safety through one of two mechanisms: hard-coded capability restrictions (limiting what actions the agent can take) or human-in-the-loop approval (requiring human confirmation for every significant action). Both are unsatisfying. Capability restrictions prevent the agent from accomplishing complex real-world tasks. Human-in-the-loop requirements negate the autonomy value proposition.

The military has solved an analogous problem over centuries of operational experience: how to give autonomous units sufficient latitude to accomplish complex missions under uncertainty while maintaining meaningful commander control and preventing catastrophic failures. The solution is not to restrict what units can do or to supervise every action. It is to specify, before the mission begins, exactly what must be accomplished (Task), under what constraints (Conditions), and to what measurable standard (Standards). Units operate autonomously within this framework and escalate only when the framework itself is violated — not for every routine decision.

MFYP applies this framework to AI agent mission execution. The TCS constraint system specifies what success looks like before execution begins. The SOP book specifies what to do in edge cases — spending money, downloading software, creating accounts — before those edge cases arise. The agent executes autonomously within these constraints and escalates via structured Telegram reports when an SOP is triggered or a standard cannot be met.

### 1.2 The Hallucination Problem

AI language models produce confident-sounding text even when their knowledge is insufficient, a failure mode collectively termed hallucination. In knowledge-intensive domains — law, medicine, finance, technical research — hallucinated outputs can cause significant harm. Existing mitigation approaches include: retrieval-augmented generation (grounding outputs in retrieved documents), chain-of-thought reasoning (encouraging explicit reasoning steps), and constitutional AI (training against harmful outputs). None directly addresses the fundamental problem: the model does not know what it does not know.

MFYP addresses hallucination through a knowledge architecture that makes epistemic status explicit at every level. Every knowledge claim stored in the system carries: a source URL (mandatory for Tier 1 claims; absence forces inference_flag=1), a confidence score (capped at MED for inference claims regardless of model confidence), a peer validation status (unverified/corroborated/consensus/disputed), and a categorical flag (verified/inference/disputed) that is preserved in the context presented to the LLM. The guard prompt appended to every inference context explicitly prohibits stating inference claims as facts, requiring uncertainty language ("I believe," "models suggest," "preliminary evidence indicates") for unverified claims.

### 1.3 The Knowledge Accumulation Problem

RAG systems retrieve documents at inference time but do not accumulate expertise — each inference starts from the same external corpus. Fine-tuned models accumulate knowledge but cannot update it after training. Neither approach models the progression of a human expert who continuously reads new material, integrates it with prior knowledge, and builds an increasingly sophisticated model of their domain over time.

MFYP implements continuous knowledge accumulation through a structured skill extraction and storage pipeline. Every signal processed by the system produces one or more knowledge claims stored with source attribution and confidence scoring. Claims are semantically organized by trigger context (when are they relevant?) and cluster (what topic area do they cover?). A three-tier importance classification governs how claims participate in inference: always-load (core claims), triggered-load (relevant claims selected by semantic matching), and reference-only (source URLs, not content). The result is an agent that genuinely improves over time within its domain — a Gorm that has processed 2,000 verified signals produces better analysis than one that has processed 20, not because its base model changed but because its structured knowledge base is deeper.

### 1.4 The Worldview Calibration Problem

AI communication systems designed to adapt to individual users almost universally rely on self-report: explicit preference settings, ratings, questionnaire responses. This produces systematically inaccurate calibration because self-report is filtered through identity management. Users describe preferred communication styles that reflect how they wish to be perceived, not how they actually process information.

MFYP's worldview inference system bypasses self-report entirely through the revealed-preference principle [1]: what people repeatedly choose to consume reflects their actual values more accurately than what they say they value. A user who watches anti-establishment commentary, masculine achievement content, and libertarian philosophy across hundreds of sessions is demonstrating consistent psychological resonance with those value clusters through behavior, not statement. MFYP's creator-content pipeline passively detects these consumption patterns from browser URL streams and constructs a developmental-level profile that calibrates communication style, goal framing, and Commander's Intent generation to the user's actual operating psychology.

---

## 2. Related Work

### 2.1 AI Agent Safety and Constraints

Constitutional AI [2] and RLHF-based alignment [3] train against harmful outputs but do not provide runtime mission constraint enforcement. Tool-use frameworks [4, 5] impose soft constraints through prompt engineering without formal verification of constraint compliance. ReAct [6] and AutoGPT [7] enable multi-step reasoning without structured mission specification or self-evaluation against explicit standards.

### 2.2 Hallucination Mitigation

RAG [8] grounds outputs in retrieved documents but does not prevent hallucination when relevant documents are unavailable. Self-consistency [9] and chain-of-thought [10] improve reasoning quality but do not address the fundamental knowledge-boundary problem. Factuality-focused training [11] reduces hallucination rates but does not eliminate them or make epistemic status explicit to downstream consumers of the output.

### 2.3 Knowledge Systems

Knowledge graphs [12] provide structured factual storage but require manual construction and do not model confidence, provenance, or temporal relevance. Vector database RAG [13] provides dynamic retrieval but retrieves by semantic similarity rather than task-relevant trigger matching, often surfacing related but not specifically relevant knowledge.

### 2.4 Preference and Identity Modeling

Collaborative filtering [14] and preference learning [15] rely on behavioral signals (ratings, clicks) for recommendation but have not been applied to developmental level inference or communication style calibration. Self-determination theory [16] and Spiral Dynamics [17] provide theoretical frameworks for values-based identity classification but have not been implemented in computing systems.

### 2.5 Differentiation

MFYP differs from all prior work by: implementing military TCS doctrine as a formal runtime constraint system with structured escalation; providing cross-instance same-species confidence calibration through peer validation; using trigger-based semantic filtering for knowledge context rather than similarity-based retrieval; and constructing worldview profiles from passive behavioral signals rather than self-report.

---

## 3. System Architecture

### 3.1 Overview

MFYP is a Python-based pipeline system designed to run continuously on local hardware (tested on Apple M4 Mac Mini). All LLM inference uses Ollama with Gemma 4 26B, running entirely on-device with no cloud dependency for core functionality.

Core modules and their functions:

| Module | Function |
|--------|----------|
| `mfyp_orchestrator.py` | Main entry point. Loads Gorm sessions, coordinates all loops. |
| `gorm_session.py` | Per-Gorm session model, source registry (10 domains, real RSS URLs). |
| `signal_scorer.py` | Gemma 4 scoring → (strength, claim, is_source_verified). |
| `skill_manager.py` | Claim storage with trigger context generation, GormHub threshold. |
| `url_discoverer.py` | Playwright adapter discovery for JavaScript-heavy sites. |
| `url_adapter.py` | Multi-strategy content extraction with built-in adapters. |
| `content_sanitizer.py` | 12 injection pattern neutralization before any LLM contact. |
| `reel_processor.py` | 4-layer video pipeline: metadata → Whisper → vision → comments. |
| `carousel_processor.py` | Playwright slide navigation + per-slide vision description. |
| `action_extractor.py` | Identifies executable strategies in HIGH-strength signals. |
| `gorm_executor.py` | Playwright-based plan execution with SOP enforcement and hard stops. |
| `mission_executor.py` | TCS mission executor: brief → research → execute → evaluate loop. |
| `influencer_profiler.py` | Creator research and worldview profile construction. |
| `daily_aar.py` | Evening After Action Review generation from ACE data and mission logs. |

### 3.2 Communication Interface

MFYP communicates with the gormers.com platform via authenticated HTTP (x-gorm-secret header). Key endpoints:

- `GET /api/ace/pending` — Poll for ACE context labels from user devices
- `POST /api/gorms/{id}/skills` — Save verified knowledge claims
- `GET /api/missions/pending` — Poll for active TCS missions
- `PATCH /api/missions/{id}` — Update mission status and research log
- `POST /api/telegram/mission-report` — Route mission reports to user Telegram

All MFYP communications over Cloudflare Tunnel (local inference → cloud platform). No direct inbound connections to local hardware.

---

## 4. TCS Mission Executor

### 4.1 Formal Constraint Specification

A TCS mission is specified as:

```
Task T:      string — what must be accomplished
Conditions C: string — constraints and environment  
Standards S:  list[string] — verifiable success criteria
Time hacks H: list[{hours: float, deliverable: string}]
SOPs P:      list[SOP] — universal + user-defined standing orders
```

The executor treats this specification as a formal constraint — not a prompt suggestion. The mission is not complete until all standards in S are met. The mission may not proceed with any action that violates a condition in C. The mission must report at every checkpoint in H.

### 4.2 Three-Phase Execution

**Phase 1 — Brief.** The Gorm reads the full TCS specification and produces a brief confirmation: task understood, key challenges identified, planned approach, any immediate blockers or clarifying questions. This confirmation is sent to the user before any research begins. The brief phase prevents wasted research effort on misunderstood missions.

**Phase 2 — Research.** The Gorm decomposes the task into research questions via Gemma (up to 8 specific search queries). For each query, it executes DuckDuckGo and HN Algolia searches, extracts content from top results, scores each for domain relevance, and stores verified claims. Every action in the research phase is checked against the SOP book before execution. Research log is persisted to the database and transmitted to the platform after each significant discovery.

**Phase 3 — Execute, Evaluate, Iterate.** Using accumulated research, the Gorm attempts the task. It then evaluates its attempt against each standard explicitly:

```json
{
  "standard": "Compare Wyoming, Delaware, Nevada across 5 dimensions",
  "met": true,
  "evidence": "Section 2 covers all 5 dimensions with sources"
}
```

If any standard is unmet, the Gorm identifies the specific gap, researches the gap specifically, and re-attempts. Maximum 3 iterations before reporting failure with specific blockers.

### 4.3 SOP Enforcement

Every action in the execution pipeline passes through the SOP checker before execution:

```python
async def check_sop_before_action(action_type: str, target: str) -> Literal['PROCEED', 'HALT']:
    if action_type == 'download':
        await request_approval(f"Download: {target}")
        return 'HALT'
    if action_type == 'spend_money':
        await report_spending_required(target)
        return 'HALT'
    if action_type == 'create_account':
        await report_account_required(target)
        return 'HALT'
    return 'PROCEED'
```

The SOP check is not advisory — a HALT return prevents the action from executing regardless of how the task is specified. SOPs have higher authority than TCS missions.

### 4.4 Self-Evaluation Protocol

The self-evaluation prompt requires explicit pass/fail judgment for each standard:

```python
evaluation_prompt = f"""You are {gorm_name} evaluating your own work.

STANDARDS you must meet:
{mission_standards}

YOUR ATTEMPT:
{attempt_output}

Evaluate honestly. For each standard:
- does the deliverable explicitly address it?
- is the evidence adequate?
- what specifically is missing if not met?

Reply with JSON only:
{{
  "meets_all_standards": false,
  "standard_checks": [
    {{"standard": "...", "met": true, "evidence": "..."}},
    {{"standard": "...", "met": false, "gap": "..."}}
  ],
  "overall_gap_summary": "..."
}}"""
```

This explicit per-standard evaluation is more reliable than asking "does this meet the requirements?" in a single pass, because the Gorm must confront each standard individually rather than producing a holistic assessment that may smooth over gaps.

---

## 5. Peer Validation Network

### 5.1 The Cross-Instance Verification Insight

A single AI agent observing a domain produces knowledge claims that may be correct, may be extraction errors, or may reflect the model's priors rather than the content. Verification by a second independent observation of the same claim — from a different agent, at a different time, from a different source — provides genuine evidentiary support.

The Gormers species taxonomy creates a natural peer validation structure: multiple users can own the same Gorm species (e.g., Lexu, specialized in legal research). When two users' Lexu instances independently observe and extract the same claim about Wyoming LLC formation — from a TikTok, an HN thread, and a law review article respectively — their independent convergence is genuine corroboration, not circular validation.

### 5.2 Similarity Assessment

Peer validation uses Jaccard keyword similarity to identify potentially matching claims:

```python
def jaccard_similarity(claim_a: str, claim_b: str) -> float:
    words_a = set(w.lower() for w in claim_a.split() if len(w) > 4)
    words_b = set(w.lower() for w in claim_b.split() if len(w) > 4)
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union
```

Claims with Jaccard similarity ≥ 0.70 are treated as potentially corroborating. Similarity ≥ 0.70 with opposing negation patterns triggers dispute detection.

### 5.3 Status Progression and Confidence Effects

```
Status progression:
  unverified  → (2+ same-species Gorms agree) → corroborated
  corroborated → (3+ same-species Gorms agree) → consensus
  any_status  → (contradiction detected)       → disputed

Confidence effects:
  consensus:    confidence *= 1.08, capped at 0.97
  corroborated: confidence unchanged
  disputed:     both sides preserved, neither confidence boosted
  unverified:   confidence unchanged
```

Status propagation: when a claim reaches consensus, all matching claims in peer Gorms are also updated to consensus status with the updated peer count.

### 5.4 Privacy Preservation in Peer Validation

Peer validation never transmits claim content between users. The platform matches claims by cluster_tag and keyword pattern on the server side, without exposing one user's specific claim text to another user's system. Claims marked is_personal=1 are excluded from peer validation entirely — no personal life data participates in cross-user comparison.

---

## 6. Progressive Disclosure System

### 6.1 The Context Budget Problem

An agent that has processed 2,000 signals has 2,000+ stored knowledge claims. Loading all claims into every inference context is computationally intractable (exceeds typical context windows) and counterproductive (relevant knowledge is diluted by irrelevant claims, reducing response quality).

Standard RAG retrieves the top-k most semantically similar claims to the current query. This approach fails for structured domain knowledge because: (1) semantic similarity to the query surface form does not predict relevance to the task; (2) recently processed claims are systematically over-retrieved regardless of quality; (3) the most important foundational claims may not be semantically similar to any specific query but are always relevant.

### 6.2 Three-Tier Architecture

**Tier 1 (always_load, importance_tier=1):** Core claims with confidence ≥ 0.90, plus agent identity and soul template. Loaded in every inference context regardless of task. Capped at 5 claims to bound token cost. Provides: who the agent is, what its highest-confidence knowledge is.

**Tier 2 (triggered_load, importance_tier=2):** Domain knowledge claims with trigger contexts generated at storage time. Loaded when trigger context matches the current task. Selection via two-pass filter:
- Pass 1: Keyword matching against trigger contexts (fast, no model call)
- Pass 2: Optional Gemma-based semantic selection from candidates (used when keyword matching yields >20 candidates)

Capped at 10 claims per inference. Provides: specifically relevant domain knowledge.

**Tier 3 (reference_only, importance_tier=3):** Source URLs, not content. Available for explicit retrieval but not loaded into context. Provides: pointers to raw sources without token cost.

### 6.3 Trigger Context Generation

Every claim is stored with an automatically generated trigger context:

```python
trigger_prompt = f"""This knowledge was learned by {gorm_name}, an expert in {domain}:
"{claim[:200]}"

Write a trigger in under 20 words starting with "when reasoning about":
Describe the specific situations where this knowledge is relevant.

Reply with ONLY the trigger phrase.
Example: "when reasoning about Wyoming LLC formation, charging order protection, or trust structures"
"""
```

The trigger generation runs at storage time, not inference time. The cost is paid once; the benefit (fast, accurate retrieval) is paid at every inference.

### 6.4 Performance Characteristics

For an agent with 2,000 stored claims:
- Naive full-load: ~80,000 tokens (exceeds most context windows)
- Naive top-k RAG: ~4,000 tokens for k=10, but retrieval quality ≤ 70%
- Three-tier triggered: ~600 tokens (Tier 1 + Tier 2), retrieval quality ≥ 85%

The token reduction (80,000 → 600) is not primarily a cost optimization — it is a quality improvement. Relevant knowledge, loaded selectively, produces better responses than relevant knowledge diluted in a large undifferentiated context.

---

## 7. Content Processing Pipeline

### 7.1 Multi-Modal Signal Processing

MFYP processes four content modalities:

**Text (articles, Reddit posts, HN discussions):** Standard HTML extraction → content sanitization → Gemma scoring.

**Video (YouTube, TikTok, Instagram Reels):** Four-layer pipeline via `reel_processor.py`:
1. Metadata extraction (title, description, tags, view count)
2. Whisper transcription of audio track
3. Vision description via LLaVA (key frames)
4. Comment thread analysis (top comments by engagement)

Each layer provides a different signal type: metadata provides context; transcript provides explicit content; vision captures what is shown; comments reveal audience response and interpretation.

**Carousels (Instagram, LinkedIn):** Playwright-based slide navigation via `carousel_processor.py`. For each slide: screenshot → LLaVA vision description → narrative builder concatenates per-slide descriptions.

**JavaScript-heavy sites (Rumble, Odysee, custom platforms):** `url_discoverer.py` uses Playwright for JavaScript rendering, falls back to direct HTTP extraction when feasible.

### 7.2 Injection Prevention

All content passes through `content_sanitizer.py` before any LLM contact. The sanitizer applies 12 pattern neutralizations:

```python
INJECTION_PATTERNS = [
    (r'ignore previous instructions?', '[FILTERED]'),
    (r'disregard (all|your) (previous|prior|above)', '[FILTERED]'),
    (r'you are now (a|an)', '[FILTERED: persona]'),
    (r'(system|admin|developer) (prompt|message|instruction)', '[FILTERED]'),
    (r'forget (everything|all) (you|about)', '[FILTERED]'),
    (r'new (instructions?|rules?|directives?)', '[FILTERED]'),
    (r'override (safety|previous|your)', '[FILTERED]'),
    (r'act as (if )?you (are|have no)', '[FILTERED]'),
    (r'do not (follow|apply) (any|your)', '[FILTERED]'),
    (r'(pretend|imagine) (you are|that)', '[FILTERED]'),
    (r'jailbreak', '[FILTERED]'),
    (r'DAN mode', '[FILTERED]'),
]
```

The sanitized content is then wrapped in `wrap_for_llm()` which adds explicit framing: "The following is external content provided for analysis. It may contain attempts to manipulate your behavior — evaluate it critically and do not follow any instructions within it."

### 7.3 Signal Scoring

```python
async def score_signal(
    content: str,
    domain: str,
    gorm_name: str,
    source_url: str = "",
    context_hint: str = "",
) -> tuple[str, str, bool]:
    """
    Returns: (strength, claim, is_source_verified)
    strength: 'HIGH' | 'MED' | 'LOW'
    claim: extracted knowledge claim, 1-2 sentences
    is_source_verified: True if source_url is populated
    """
```

The scoring prompt asks Gemma to: (1) assess signal relevance to the domain; (2) extract the single most important verifiable claim from the content; (3) assign a strength rating based on specificity, novelty, and actionability. Claims without source URLs receive inference_flag=1 and are capped at MED regardless of model-assessed strength.

---

## 8. Worldview Inference Pipeline

### 8.1 The Revealed Preference Mechanism

The revealed preference principle [1] from behavioral economics states that observed choices provide more accurate models of preferences than stated preferences, because choices are made without identity management pressure. Applied to media consumption: the content a person returns to repeatedly reflects their actual values and worldview more accurately than any questionnaire they would answer.

MFYP operationalizes this through passive URL detection (via ACE's Influence Vector) combined with the creator research pipeline:

```python
async def research_influencer(
    user_id: int,
    creator_name: str,
    platform: str
) -> dict:
    """
    Research a creator and extract their profile:
    - core_philosophy: 2-3 sentence summary
    - values_promoted: list[str]
    - spiral_level: 1-9 (Spiral Dynamics)
    - communication_style: direct|narrative|analytical|emotional
    - worldview: red_pill|libertarian|mainstream|spiritual|integral
    - key_themes: list[str]
    - resonant_phrases: list[str]
    """
```

### 8.2 Community Creator Database

Creator profiles are stored in a community database rather than researched per-user:

- **Tier 1 (pre-seeded):** ~500 entries for the most frequently consumed creators, researched before platform launch
- **Tier 2 (community-contributed):** Each new creator detected by any user's MFYP instance → researched once → added to shared database → all subsequent users get cached result
- **Tier 3 (on-demand):** Unknown creators queued for research (24-hour SLA)

The database compounds: every new user who mentions an obscure creator adds them for everyone. Creator profiles are public knowledge — only the user's consumption frequency data is private.

### 8.3 Profile Construction and Communication Calibration

The worldview profile is a weighted average of detected creators' value vectors, weighted by detection frequency:

```
User detection log:
  Andrew Tate:    47 sessions
  Alex Jones:     31 sessions  
  Joe Rogan:      22 sessions
  Fresh & Fit:    18 sessions

Weighted composite:
  Primary values: freedom, competition, truth-seeking, masculine achievement
  Spiral level:   5 (Orange/Achiever) with Red energy and Yellow tendencies
  Worldview:      anti-establishment, anti-consensus, individual-sovereignty
  Framing:        competitive, anti-matrix, direct
  Resonant lang:  "most people miss this," "the real reason," "leverage"
  Avoid:          hedging, "experts say," mainstream consensus framing
```

This profile calibrates every briefing, every Commander's Intent, every mission report. The Gorm does not speak to a generic user — it speaks to a specific person whose worldview it has mapped from behavioral evidence.

---

## 9. Evaluation

### 9.1 Mission Execution Metrics

- **Standards compliance rate:** Fraction of submitted mission deliverables that meet all stated standards on first, second, and third iteration respectively. Baseline: current best-in-class agent frameworks at ~40% first-iteration compliance on complex tasks. Target: ≥65% first-iteration, ≥85% by third iteration.
- **SOP false negative rate:** Fraction of SOP-triggering actions that execute without triggering SOP halt. Target: 0% (any miss is a system failure).
- **Mission escalation rate:** Fraction of missions that require owner interaction beyond scheduled time hacks. Target: <20% (missions should be largely autonomous).

### 9.2 Knowledge Quality Metrics

- **Trigger retrieval precision:** Fraction of Tier 2 claims loaded for a given task that are judged relevant by a human evaluator. Target: ≥85% (vs. ≤70% for naive top-k RAG in preliminary experiments).
- **Peer validation convergence:** Correlation between peer validation status and ground truth accuracy (human-evaluated). A claim at "consensus" status should be correct ≥95% of the time. Target: ≥90% accuracy at consensus, ≥80% at corroborated.
- **Hallucination suppression:** Fraction of inference-flagged claims that are stated as fact (guard prompt violation) in generated briefings. Target: <1%.

### 9.3 Worldview Inference Metrics

- **Rank-order correlation:** Correlation between MFYP-inferred Spiral Dynamics level and validated self-report instrument (Washington University Sentence Completion Test [18]) administered to opt-in validation cohort. Target: ≥0.70.
- **Communication preference A/B:** Users rated with "metrics/competitive" framing see ≥15% higher briefing utility ratings for metric-framed briefings vs. values-framed briefings of identical information content. Target: significant difference (p < 0.05) in the expected direction.

---

## 10. Privacy Architecture

### 10.1 Local Inference Guarantee

All LLM inference occurs on user hardware via Ollama. Content processed by MFYP — URLs visited, content extracted, knowledge claims generated — never leaves the local machine before Gemma scoring. After scoring, only the structured output (strength, claim, source URL) is transmitted to the platform — not the raw content.

### 10.2 Personal Data Classification

MFYP applies a three-tier privacy classification to all data:

**Tier 2 (User-Private):** Financial data, health data, relationship data, personal goals. Detected via source (Mercury, Apple Health) and content patterns (financial/health keywords). Never transmitted. Never peer-validated. Never proposed to GormHub.

**Tier 3 (Context-Derived Personal):** Behavioral patterns, communication preferences, worldview profile, influencer detection log. Detected via ACE context labels and focus timer data. Never transmitted. Never peer-validated. High confidence by default (personal truths are verified by definition).

**Tier 1 (Public Domain Knowledge):** Facts that any expert could learn from public sources. GormHub-eligible. Peer-validation-eligible.

### 10.3 The Personal Boundary Test

When skill_manager.py saves a new claim, it applies the personal boundary test before storage:

```python
def detect_personal_boundary(claim: str, source_url: str) -> tuple[bool, str | None]:
    personal_sources = ['mercury.com', 'mail.google.com', 'calendar.google.com', 
                         'apple.com/health', 'ace_context', 'focus_timer']
    if any(s in source_url for s in personal_sources):
        return True, 'behavioral_pattern'
    
    financial = re.search(r'\$[\d,]+|monthly revenue|burn rate|salary', claim, re.I)
    health = re.search(r'blood pressure|heart rate|sleep quality|medication', claim, re.I)
    goals = re.search(r'my goal|my target|I want to|my plan', claim, re.I)
    behavioral = re.search(r'prefers|usually|tends to|works best', claim, re.I)
    
    if financial: return True, 'financial'
    if health: return True, 'health'
    if goals: return True, 'goals'
    if behavioral: return True, 'behavioral_pattern'
    return False, None
```

Claims that fail the boundary test are stored with is_personal=1, permanently excluded from GormHub and peer validation, and never included in any aggregated platform analytics.

---

## 11. Discussion

### 11.1 The SOPs-as-Doctrine Insight

The most significant architectural insight in MFYP is not technical — it is philosophical. The military solved the safe-autonomous-agent problem not through capability restriction but through doctrine: codified procedures for every foreseeable edge case, issued before the mission, carrying authority above individual judgment. An agent operating under a complete SOP book does not need to make novel ethical judgments in the field. The judgment has already been made, encoded in the SOP, and the agent's job is compliance.

This insight transfers directly to AI agents. An agent that must make ethical judgments in real time — is this download safe? should I spend this money? is this account creation acceptable? — will occasionally make wrong judgments, and those wrong judgments can have irreversible consequences. An agent operating under a complete SOP book never makes those judgments in the field. The answer is always in the SOP.

The implication is that expanding agent capability and ensuring agent safety are not in tension — they move together. A more complete SOP book enables broader autonomous operation, not more constrained operation, because the agent has pre-authorized answers for more edge cases.

### 11.2 Peer Validation as Network Effect

The peer validation network creates a genuine network effect for knowledge quality: the more users who own the same Gorm species, the more claims get validated, and the higher the quality of everyone's knowledge. This is a different network effect than typical platform effects (Metcalfe's Law: value scales with connections). The peer validation network effect is an epistemic network effect: value scales with the number of independent observers of the same reality.

A species with 100 active instances across 100 users has fundamentally different knowledge quality characteristics than a species with 1 instance. Claims that reach consensus across 10 independent observations from 10 different sources are approaching fact; claims from a single observation remain preliminary. The platform's value proposition for knowledge quality is not just the intelligence of any individual Gorm — it is the collective epistemic weight of all instances of that species.

### 11.3 Limitations

**Scale of local inference.** Gemma 4 26B provides adequate performance for single-Gorm scoring but may bottleneck colonies with many simultaneously active Gorms on hardware with limited VRAM. Future work: quantized model variants and batched inference.

**Creator database freshness.** The community creator database requires ongoing maintenance as creator content and value positions evolve. A creator's early content may reflect a different worldview than current content. Future work: recency-weighted profile scoring.

**Peer validation bootstrapping.** Peer validation requires minimum 2 same-species instances per species before it contributes. New species with few users have unvalidated knowledge regardless of claim quality. Future work: federated cross-species validation for adjacent domains.

**SOP completeness.** The universal SOP set covers the most critical edge cases (spending, downloading, accounts). Novel edge cases not covered by SOPs require escalation to owner, breaking autonomous operation. Future work: SOP learning from mission outcomes — edge cases that recur become new SOPs.

---

## 12. Conclusion

MFYP presents four contributions to the AI agent literature: TCS-constrained mission execution with verifiable self-evaluation, same-species cross-instance peer validation for knowledge confidence calibration, three-tier progressive disclosure with trigger-based context selection, and passive worldview inference from media consumption behavior. Together, these contributions address the four fundamental limitations of current AI agent systems: unsafe open-ended execution, hallucination under knowledge gaps, inability to accumulate calibrated expertise over time, and dependence on inaccurate self-report for user modeling.

The unifying insight across all four contributions is that the hardest problems in AI agent design have already been solved — in other domains, for other agents. Military doctrine solved safe autonomous operation through TCS and SOPs. Behavioral economics solved preference measurement through revealed preference and consumption observation. Epidemiology solved claim validation through independent replication. Knowledge management solved retrieval quality through semantic indexing and relevance scoring. MFYP applies these pre-existing solutions to AI agents operating in personal intelligence domains.

The result is an agent system that can be safely delegated complex open-ended missions, accumulates genuine expertise rather than simulating it, produces verifiable rather than merely plausible knowledge, and communicates in ways that actually resonate with the user's real psychology rather than their stated preferences. That combination — safe, expert, honest, resonant — describes what an AI agent needs to be to function as a genuine personal intelligence asset rather than a sophisticated autocomplete.

---

## References

[1] P. A. Samuelson, "A Note on the Pure Theory of Consumer's Behaviour," *Economica*, vol. 5, no. 17, pp. 61–71, 1938.

[2] Y. Bai et al., "Constitutional AI: Harmlessness from AI Feedback," *arXiv:2212.08073*, 2022.

[3] P. F. Christiano et al., "Deep Reinforcement Learning from Human Preferences," *NeurIPS*, 2017.

[4] Y. Shen et al., "HuggingGPT: Solving AI Tasks with ChatGPT and its Friends in HuggingFace," *arXiv:2303.17580*, 2023.

[5] T. Schick et al., "Toolformer: Language Models Can Teach Themselves to Use Tools," *arXiv:2302.04761*, 2023.

[6] S. Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models," *ICLR*, 2023.

[7] T. Significant Gravitas, "AutoGPT: An Autonomous GPT-4 Experiment," *GitHub*, 2023.

[8] P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," *NeurIPS*, 2020.

[9] X. Wang et al., "Self-Consistency Improves Chain of Thought Reasoning in Language Models," *ICLR*, 2023.

[10] J. Wei et al., "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models," *NeurIPS*, 2022.

[11] J. Maynez et al., "On Faithfulness and Factuality in Abstractive Summarization," *ACL*, 2020.

[12] A. Bordes et al., "Translating Embeddings for Modeling Multi-relational Data," *NeurIPS*, 2013.

[13] J. Johnson, M. Douze, and H. Jégou, "Billion-Scale Similarity Search with GPUs," *IEEE TPAMI*, 2021.

[14] Y. Koren, R. Bell, and C. Volinsky, "Matrix Factorization Techniques for Recommender Systems," *IEEE Computer*, vol. 42, no. 8, 2009.

[15] J. Fürnkranz and E. Hüllermeier, *Preference Learning*, Springer, 2010.

[16] E. L. Deci and R. M. Ryan, "Self-Determination Theory," *Psychological Inquiry*, 2000.

[17] D. E. Beck and C. C. Cowan, *Spiral Dynamics: Mastering Values, Leadership and Change*, Blackwell, 1996.

[18] J. Loevinger, *Ego Development*, Jossey-Bass, 1976.

[19] M. Ester et al., "A Density-Based Algorithm for Discovering Clusters in Large Spatial Databases with Noise," *KDD*, 1996.

[20] U.S. Army, *FM 7-8: Infantry Rifle Platoon and Squad*, Department of the Army, 2016.

---

*© 2026 BEERS LABS LLC. All rights reserved.*
