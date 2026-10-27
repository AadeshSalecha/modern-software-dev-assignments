# Folder taxonomy and cues

The single source of truth for where a Hyfin file belongs. It mirrors the team's ClickUp Space/Folder structure and the six-workstream org chart. Classify against this list, not against memory of what the tree "should" look like.

## Tree (inside the Hyfin Team Drive root)

```
00-Needs-Review/
01-Guarantees/
├── Cambodia-EVGF/
├── BRD/
├── Dhamana/
├── CEFIL-NCGCL-Guarantee/
└── Other-Guarantees-PH-Malaysia-Ethiopia-Agrivoltaics/
02-Funds/
├── AssetCo-Pipeline/
├── CAFF/
├── CMRF/
└── CEFIL-Green-NBFC/
03-GAIA/
├── Tara-Deliverable/
├── OEM-AVL-Agent/
├── Credit-Assessment-Agent-GAIA-Roadmap/
└── News-Agent/
04-Fund-Forge/
05-BUS/
06-Org-Team/
├── Front-Office/
│   └── Advisory-Board/
├── Back-Office/
├── Team-Hiring/
└── AI-Native-Org/
```

Some of these folders may not exist yet. Look them up by exact title under the root at run time; never hard-code folder IDs. Create a missing one only when an approved move needs it, parents first.

`00-Needs-Review` is not a workstream. It is the parking lot for sensitive files and for Hyfin files that don't fit anywhere with reasonable confidence. Never guess a destination for a file that belongs there.

## Cues

Match on filename, the current My Drive folder or path, and the title. Cues are illustrative, not exhaustive: a file that clearly fits a bucket by subject matter goes there even without the literal keyword. Any cue below also counts as a Hyfin signal for the gate.

| Folder | Cues |
|---|---|
| Cambodia-EVGF | "EVGF", "Cambodia", "[REDACTED]", "AVL" (when paired with Cambodia) |
| BRD | "BRD", "[REDACTED]" + guarantee/facility context |
| Dhamana | "Dhamana", Islamic finance / risk-sharing guarantee structuring |
| CEFIL-NCGCL-Guarantee | "CEFIL", "NCGCL", "Pakistan" + guarantee/facility context |
| Other-Guarantees-PH-Malaysia-Ethiopia-Agrivoltaics | "PhilGuar", "Philippines", "Malaysia", "Ethiopia", "Agrivoltaics", "Renew2030" + guarantee context |
| AssetCo-Pipeline | "AssetCo", named opportunities ([REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED], [REDACTED]), "[REDACTED]", "[REDACTED]" |
| CAFF | "CAFF", "Catalytic Aggregation", "CORE Anchor Fund", "anchor fund" |
| CMRF | "CMRF", "Clean Mobility Receivables", "[REDACTED]" + fund context |
| CEFIL-Green-NBFC | "CEFIL", "Green NBFC", "Pakistan" + fund/lending context (not guarantee) |
| Tara-Deliverable | "Tara", "financial institution mapping", "FI mapping", "[REDACTED]" |
| OEM-AVL-Agent | "OEM", "AVL", "Approved Vendor List", "[REDACTED]" |
| Credit-Assessment-Agent-GAIA-Roadmap | "Credit Assessment Agent", "Cap Stack Agent", "BUS Agent" (legacy names), "GAIA roadmap" |
| News-Agent | "News Agent", market/news monitoring for GAIA |
| 04-Fund-Forge | "Fund Forge", "[REDACTED]" |
| 05-BUS | "The BUS", "back-up servicer", "[REDACTED]" |
| Front-Office | front-office ops, deal-facing admin not tied to a specific vehicle |
| Advisory-Board | "advisory board", board member recruitment/bios |
| Back-Office | ops, bookkeeping, [REDACTED], [REDACTED], benefits admin (run the sensitivity check first) |
| Team-Hiring | job descriptions, hiring pipeline, interview notes (not individual comp; run the sensitivity check first) |
| AI-Native-Org | internal AI tooling, prompts, Claude Projects/skills documentation, sprint process |

Generic Hyfin signals that pass the gate without picking a folder: "Hyfin", "GAIA", "CORE", a named Hyfin vehicle, a Hyfin teammate's name in a Hyfin context.

## Tie-breaks

- Two plausible folders: the more specific one. "CEFIL" plus "guarantee" goes to `CEFIL-NCGCL-Guarantee`; "CEFIL" plus "NBFC" or "lending" goes to `CEFIL-Green-NBFC`; "CEFIL" alone is low confidence, so `00-Needs-Review` with reason `unclear match`.
- "AVL" alone goes to `OEM-AVL-Agent`; "AVL" with "Cambodia" goes to `Cambodia-EVGF`.
- A person's name alone is never enough for a folder; it needs the stated context.
- Cross-cutting documents for one workstream (overview, tracker, roadmap-adjacent) go in the workstream's top folder, not a forced sub-item.
