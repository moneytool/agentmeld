# miner v3 summary — v3.jsonl

mined ok: 2421; active non-fork non-archived: 2255

## RQ1 — how many tools per repo (active set)

- 1 tool(s): 1109 (49.2%)
- 2 tool(s): 614 (27.2%)
- 3 tool(s): 305 (13.5%)
- 4 tool(s): 156 (6.9%)
- 5 tool(s): 40 (1.8%)
- 6 tool(s): 16 (0.7%)
- 7 tool(s): 14 (0.6%)
- 8 tool(s): 1 (0.0%)

≥2 tools: 1146 (50.8%)
(Sampling frame: repos found by searching for one of five instruction files, so every repo has ≥1 tool; multiplicity is conditional on that. Size-stratified search; not population-weighted.)

≥2 tools by seed file: .cursorrules: 57.8%, .github/copilot-instructions.md: 46.6%, AGENTS.md: 44.6%, CLAUDE.md: 36.7%, GEMINI.md: 70.5%

Top combinations:

- agents-md + claude-code: 281
- agents-md + claude-code + gemini-cli: 130
- agents-md + claude-code + copilot: 71
- claude-code + cursor: 66
- agents-md + claude-code + copilot + gemini-cli: 63
- agents-md + copilot: 59
- claude-code + copilot: 53
- agents-md + claude-code + cursor: 50
- claude-code + gemini-cli: 48
- agents-md + claude-code + copilot + cursor: 43
- agents-md + gemini-cli: 38
- agents-md + cursor: 36

## RQ2 — mechanism for each co-existing pair (active set)


### AGENTS.md~CLAUDE.md (n=696)

- distinct: 326 (46.8%)
- import_pointer: 86 (12.4%)
- prose_pointer: 83 (11.9%)
- symlink_to_primary: 67 (9.6%)
- overlapping: 52 (7.5%)
- near_identical: 40 (5.7%)
- identical: 21 (3.0%)
- primary_symlink_other: 14 (2.0%)
- corrupted_plain_pointer: 4 (0.6%)
- symlink_other: 2 (0.3%)
- unavailable: 1 (0.1%)

### AGENTS.md~GEMINI.md (n=318)

- distinct: 176 (55.3%)
- overlapping: 35 (11.0%)
- prose_pointer: 33 (10.4%)
- identical: 27 (8.5%)
- near_identical: 18 (5.7%)
- import_pointer: 14 (4.4%)
- symlink_to_primary: 8 (2.5%)
- primary_symlink_other: 4 (1.3%)
- corrupted_plain_pointer: 1 (0.3%)
- symlink_other: 1 (0.3%)
- unavailable: 1 (0.3%)

### CLAUDE.md~GEMINI.md (n=317)

- distinct: 167 (52.7%)
- identical: 48 (15.1%)
- overlapping: 45 (14.2%)
- near_identical: 37 (11.7%)
- symlink_to_primary: 9 (2.8%)
- prose_pointer: 5 (1.6%)
- primary_symlink_other: 4 (1.3%)
- import_pointer: 1 (0.3%)
- unavailable: 1 (0.3%)

### AGENTS.md~.github/copilot-instructions.md (n=316)

- distinct: 219 (69.3%)
- overlapping: 38 (12.0%)
- prose_pointer: 37 (11.7%)
- primary_symlink_other: 10 (3.2%)
- identical: 5 (1.6%)
- near_identical: 5 (1.6%)
- unavailable: 2 (0.6%)

### AGENTS.md~.cursorrules (n=154)

- distinct: 110 (71.4%)
- prose_pointer: 21 (13.6%)
- overlapping: 9 (5.8%)
- identical: 6 (3.9%)
- symlink_to_primary: 3 (1.9%)
- primary_symlink_other: 2 (1.3%)
- import_pointer: 1 (0.6%)
- symlink_other: 1 (0.6%)
- near_identical: 1 (0.6%)

### AGENTS.md~.windsurfrules (n=31)

- distinct: 18 (58.1%)
- prose_pointer: 5 (16.1%)
- overlapping: 4 (12.9%)
- symlink_to_primary: 2 (6.5%)
- near_identical: 1 (3.2%)
- identical: 1 (3.2%)

### AGENTS.md~.clinerules (n=21)

- distinct: 12 (57.1%)
- prose_pointer: 5 (23.8%)
- symlink_to_primary: 1 (4.8%)
- near_identical: 1 (4.8%)
- overlapping: 1 (4.8%)
- identical: 1 (4.8%)

### AGENTS.md~codex.md (n=4)

- distinct: 2 (50.0%)
- near_identical: 1 (25.0%)
- prose_pointer: 1 (25.0%)

### AGENTS.md~AGENT.md (n=2)

- distinct: 2 (100.0%)

## RQ5 — breakage

- corrupted symlinks (XSym / plain pointer): 4
  - kupzed/catatz: ['AGENTS.md~CLAUDE.md', 'AGENTS.md~GEMINI.md']
  - setuq-in/setuq: ['AGENTS.md~CLAUDE.md']
  - ArisGuimera/MobiAI-Core: ['AGENTS.md~CLAUDE.md']
  - eiriksgata/wc3-map-ts-template: ['AGENTS.md~CLAUDE.md']
- imports pointing at a missing ROOT file (verified against the root tree): 5
  - diraigent/diraigent: ['@AGENTS.md']
  - vichannnnn/holy-grail: ['@ROADMAP.md']
  - dtaylor1701/XCSnippets: ['@./Design.md', '@./Product.md']
  - Curiosity-Ai-BV/localOCR: ['@Updates.md']
  - rfabbri/minus: ['@README_INTERNAL.md', '@README_INTERNAL.md']
- imports to nested paths, existence NOT yet verified (needs follow-up fetch): 58

## RQ6 — is AGENTS.md canonical?

- repos with AGENTS.md: 1171 (51.9% of active)
- of those, at least one other tool file points at it: 266 (22.7%)

## RQ4 (prep) — file age and edit counts

- CLAUDE.md: n=1179, median lifetime 3 days, median commits 2
- AGENTS.md: n=1171, median lifetime 11 days, median commits 3
- .github/copilot-instructions.md: n=670, median lifetime 0 days, median commits 2
- GEMINI.md: n=530, median lifetime 0 days, median commits 1
- .cursorrules: n=408, median lifetime 0 days, median commits 1
- .windsurfrules: n=44, median lifetime 0 days, median commits 1
- .clinerules: n=26, median lifetime 0 days, median commits 1
- AGENT.md: n=9, median lifetime 10 days, median commits 2
- codex.md: n=7, median lifetime 0 days, median commits 2
