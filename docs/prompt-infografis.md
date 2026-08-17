# Prompt — Infografis ARKA (image generation)

Create a professional vertical INFOGRAPHIC for an AI hackathon project.

PROJECT:
ARKA — Asset Reliability Knowledge Agent
An autonomous multi-agent system for multi-plant FMCG manufacturing (fictional, 6–8 beverage plants).
Built on Google ADK, deployed on Cloud Run / Vertex AI Agent Engine.

PURPOSE:
The infographic must clearly explain what ARKA is, what problem it solves, how it works, and what
value it provides. Prioritize information clarity and visual storytelling over decorative visuals.
ARKA is NOT a chatbot — chat is only one interface into the Investigator agent. Show autonomy.

MAIN MESSAGE:
ARKA turns scattered maintenance history across many plants into evidence-cited reliability
findings and ready-to-sign documents, decided by AI reasoning but with every number computed
deterministically by code.

LAYOUT:
Clean vertical infographic, clear top-to-bottom information hierarchy.

SECTION 1 — TITLE
At the top:
ARKA
Asset Reliability Knowledge Agent

Tagline:
"From historical asset knowledge to actionable reliability insights."

SECTION 2 — THE PROBLEM
Visually show fragmented asset knowledge across separate plants:
- historical work orders and maintenance reports
- inspection documents
- free-text failure notifications
- asset master data and spare part records
- knowledge that never crosses plant boundaries

Represent these as document/data sources scattered across separate plant silos, hard to search
and connect manually. Core pain: the same failure repeats in a different plant, and is paid for
from zero every single time.

SECTION 3 — HOW ARKA WORKS
Clear top-to-bottom process flow, with ARKA as the central intelligence layer:

Historical Asset Knowledge (work orders · inspections · notifications · spare parts)
↓
Knowledge Retrieval (graph traversal + vector search over documents — GraphRAG)
↓
AI Reasoning (which case to pursue, how deep, when to escalate to a human)
↓
Reliability Analysis (deterministic scoring · cross-plant precedent · dynamic spare part criticality)
↓
Actionable Insights (cited memo · infographic · escalation)

Optionally show the five specialised agents as one chain, each owning exactly one decision:
Scout (what is worth investigating) → Investigator (next retrieval step, when to escalate) →
Reporter (which blocks enter the document and in what order) → Designer (visual emphasis and form),
with Curator (which mappings are safe to auto-approve) running orthogonally beside the chain.

SECTION 4 — ARKA ARCHITECTURE
Simplified visual architecture with arrows showing information flow:
1. Asset Documents & Historical Records (work orders, inspection reports, notifications, master data)
2. Knowledge Base / Retrieval Layer (property graph + vector index over document chunks)
3. ARKA AI Agent (multi-agent chain on Google ADK)
4. Reliability Reasoning (deterministic scoring engine — symptom overlap, component match,
   corroboration, recency; plus dynamic spare part criticality)
5. User / Maintenance Team (reliability engineers receive cited documents and escalations)

Show a clear separation line in the reasoning layer: DETERMINISTIC (all scores, numbers, charts,
citations, graph traversal) vs LLM (which path to follow, how to read free text, which blocks to
select, how to phrase narrative). The model never touches a number.
Also show the human-in-the-loop gate: agent findings enter the graph only as unreviewed candidates
awaiting human approval.

SECTION 5 — OUTPUT / VALUE
Concise outcomes, each with a simple icon:
- Faster cross-plant knowledge retrieval
- Context-aware, evidence-cited answers
- Cross-plant precedent found automatically
- Dynamic spare part criticality (supply-chain aware)
- Publication-ready memo / official note / report (PDF, with citations)
- Better maintenance decision support, with clear escalation when evidence is ambiguous

SECTION 6 — FINAL VALUE PROPOSITION
At the bottom, emphasize:

"Turn accumulated asset knowledge into actionable reliability intelligence."

DESIGN STYLE:
- Premium enterprise technology infographic.
- Professional corporate visual language.
- Clean information architecture.
- Modern AI and industrial asset reliability aesthetic.
- Deep navy / near-black base (#090d16, #0f172a panels) with white text (#f8fafc), slate-grey
  secondary text (#94a3b8), and controlled blue (#3b82f6) / cyan (#06b6d4) accents.
  Use emerald (#10b981) and amber (#f59e0b) very sparingly, only for status accents.
- Strong contrast.
- Consistent typography.
- Clean geometric shapes; subtle rounded card panels with thin light borders.
- Subtle data visualization and knowledge graph elements (nodes and edges connecting plants).
- Minimal decorative elements.
- Generous spacing between sections.
- Clear arrows and connectors.
- Every section visually distinct but part of one coherent system.

TYPOGRAPHY:
Modern professional sans-serif.
ARKA is the largest title.
Section headings clearly distinguishable from body text.
All text correctly spelled and highly readable.
Do not use excessive text.
Do not generate fake statistics, fake company logos, fake metrics, or irrelevant labels.
Do not name any real company, real plant location, or real industrial software product —
the domain is a fictional multi-plant FMCG manufacturer.

INFORMATION DESIGN:
Understandable within 5–10 seconds at a glance. A viewer should immediately understand:
1. What ARKA is. 2. What problem it solves. 3. How ARKA works. 4. What output it produces.
5. Why it is valuable.

VISUAL PRIORITY:
Information clarity > decorative visuals.
Diagram clarity > visual effects.
Readable typography > complex imagery.

QUALITY:
Extremely clean and sharp. Crisp edges. Clear diagrams. Consistent iconography.
No blurry elements. No distorted text. No malformed letters. No duplicated objects.
No random text. No watermark.

FORMAT:
Vertical infographic, portrait orientation, suitable for presentation and digital display.
