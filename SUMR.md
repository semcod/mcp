# Autonomiczny Agent Refaktoryzacji MCP

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Call Graph](#call-graph)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `mcp`
- **version**: `0.0.0`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: app.doql.less, goal.yaml, .env.example, docker-compose.yml, project/(5 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: mcp;
  version: 0.1.0;
}

interface[type="api"] {
  type: rest;
  framework: fastapi;
}

integration[name="github"] {
  type: scm;
}

deploy {
  target: docker-compose;
  compose_file: docker-compose.yml;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
}

environment[name="prod"] {
  runtime: docker-compose;
}
```

## Call Graph

*13 nodes · 9 edges · 9 modules · CC̄=2.9*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in scripts.test)* | 0 | 26 | 0 | **26** |
| `chat_completions` *(in mcp-gateway.server)* | 6 | 0 | 26 | **26** |
| `main` *(in llm-agent.agent_standalone)* | 2 | 0 | 21 | **21** |
| `main` *(in git2mcp.examples.03_agent_git2mcp)* | 4 | 0 | 19 | **19** |
| `main` *(in git2mcp.examples.01_sync_and_commit)* | 1 | 0 | 18 | **18** |
| `main` *(in llm-agent.agent)* | 2 | 0 | 16 | **16** |
| `main` *(in git2mcp.examples.02_fragment_sync_to_skills)* | 1 | 0 | 15 | **15** |
| `main` *(in dashboard.server)* | 2 | 0 | 10 | **10** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp
# nodes: 13 | edges: 9 | modules: 9
# CC̄=2.9

HUBS[20]:
  scripts.test.print
    CC=0  in:26  out:0  total:26
  mcp-gateway.server.chat_completions
    CC=6  in:0  out:26  total:26
  llm-agent.agent_standalone.main
    CC=2  in:0  out:21  total:21
  git2mcp.examples.03_agent_git2mcp.main
    CC=4  in:0  out:19  total:19
  git2mcp.examples.01_sync_and_commit.main
    CC=1  in:0  out:18  total:18
  llm-agent.agent.main
    CC=2  in:0  out:16  total:16
  git2mcp.examples.02_fragment_sync_to_skills.main
    CC=1  in:0  out:15  total:15
  dashboard.server.main
    CC=2  in:0  out:10  total:10
  mcp-webui.server.index
    CC=3  in:0  out:10  total:10
  mcp-gateway.server.authenticate
    CC=4  in:0  out:8  total:8
  mcp-gateway.server.audit
    CC=1  in:1  out:5  total:6
  mcp-gateway.server.find_tenant_by_key
    CC=3  in:1  out:2  total:3
  mcp-webui.server.gateway_headers
    CC=1  in:2  out:0  total:2

MODULES:
  dashboard.server  [1 funcs]
    main  CC=2  out:10
  git2mcp.examples.01_sync_and_commit  [1 funcs]
    main  CC=1  out:18
  git2mcp.examples.02_fragment_sync_to_skills  [1 funcs]
    main  CC=1  out:15
  git2mcp.examples.03_agent_git2mcp  [1 funcs]
    main  CC=4  out:19
  llm-agent.agent  [1 funcs]
    main  CC=2  out:16
  llm-agent.agent_standalone  [1 funcs]
    main  CC=2  out:21
  mcp-gateway.server  [4 funcs]
    audit  CC=1  out:5
    authenticate  CC=4  out:8
    chat_completions  CC=6  out:26
    find_tenant_by_key  CC=3  out:2
  mcp-webui.server  [2 funcs]
    gateway_headers  CC=1  out:0
    index  CC=3  out:10
  scripts.test  [1 funcs]
    print  CC=0  out:0

EDGES:
  git2mcp.examples.02_fragment_sync_to_skills.main → scripts.test.print
  mcp-webui.server.index → mcp-webui.server.gateway_headers
  git2mcp.examples.03_agent_git2mcp.main → scripts.test.print
  git2mcp.examples.01_sync_and_commit.main → scripts.test.print
  dashboard.server.main → scripts.test.print
  llm-agent.agent.main → scripts.test.print
  llm-agent.agent_standalone.main → scripts.test.print
  mcp-gateway.server.authenticate → mcp-gateway.server.find_tenant_by_key
  mcp-gateway.server.chat_completions → mcp-gateway.server.audit
```

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp
# nodes: 13 | edges: 9 | modules: 9
# CC̄=2.9

HUBS[20]:
  scripts.test.print
    CC=0  in:26  out:0  total:26
  mcp-gateway.server.chat_completions
    CC=6  in:0  out:26  total:26
  llm-agent.agent_standalone.main
    CC=2  in:0  out:21  total:21
  git2mcp.examples.03_agent_git2mcp.main
    CC=4  in:0  out:19  total:19
  git2mcp.examples.01_sync_and_commit.main
    CC=1  in:0  out:18  total:18
  llm-agent.agent.main
    CC=2  in:0  out:16  total:16
  git2mcp.examples.02_fragment_sync_to_skills.main
    CC=1  in:0  out:15  total:15
  dashboard.server.main
    CC=2  in:0  out:10  total:10
  mcp-webui.server.index
    CC=3  in:0  out:10  total:10
  mcp-gateway.server.authenticate
    CC=4  in:0  out:8  total:8
  mcp-gateway.server.audit
    CC=1  in:1  out:5  total:6
  mcp-gateway.server.find_tenant_by_key
    CC=3  in:1  out:2  total:3
  mcp-webui.server.gateway_headers
    CC=1  in:2  out:0  total:2

MODULES:
  dashboard.server  [1 funcs]
    main  CC=2  out:10
  git2mcp.examples.01_sync_and_commit  [1 funcs]
    main  CC=1  out:18
  git2mcp.examples.02_fragment_sync_to_skills  [1 funcs]
    main  CC=1  out:15
  git2mcp.examples.03_agent_git2mcp  [1 funcs]
    main  CC=4  out:19
  llm-agent.agent  [1 funcs]
    main  CC=2  out:16
  llm-agent.agent_standalone  [1 funcs]
    main  CC=2  out:21
  mcp-gateway.server  [4 funcs]
    audit  CC=1  out:5
    authenticate  CC=4  out:8
    chat_completions  CC=6  out:26
    find_tenant_by_key  CC=3  out:2
  mcp-webui.server  [2 funcs]
    gateway_headers  CC=1  out:0
    index  CC=3  out:10
  scripts.test  [1 funcs]
    print  CC=0  out:0

EDGES:
  git2mcp.examples.02_fragment_sync_to_skills.main → scripts.test.print
  mcp-webui.server.index → mcp-webui.server.gateway_headers
  git2mcp.examples.03_agent_git2mcp.main → scripts.test.print
  git2mcp.examples.01_sync_and_commit.main → scripts.test.print
  dashboard.server.main → scripts.test.print
  llm-agent.agent.main → scripts.test.print
  llm-agent.agent_standalone.main → scripts.test.print
  mcp-gateway.server.authenticate → mcp-gateway.server.find_tenant_by_key
  mcp-gateway.server.chat_completions → mcp-gateway.server.audit
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 52f 5714L | python:19,yaml:13,txt:6,shell:5,yml:2,toml:1 | 2026-05-03
# CC̄=2.9 | critical:6/172 | dups:0 | cycles:0

HEALTH[6]:
  🟡 CC    compute_metrics CC=15 (limit:15)
  🟡 CC    _sync_from_git_proxy CC=15 (limit:15)
  🟡 CC    _compute_metrics_for_repo CC=15 (limit:15)
  🟡 CC    _recommend_refactoring CC=15 (limit:15)
  🟡 CC    compute_metrics_for_repo CC=15 (limit:15)
  🟡 CC    detect_code_patterns CC=15 (limit:15)

REFACTOR[1]:
  1. split 6 high-CC methods  (CC>15)

PIPELINES[140]:
  [1] Src [main]: main → print
      PURITY: 100% pure
  [2] Src [main]: main → print
      PURITY: 100% pure
  [3] Src [__init__]: __init__
      PURITY: 100% pure
  [4] Src [_request]: _request
      PURITY: 100% pure
  [5] Src [health]: health
      PURITY: 100% pure

LAYERS:
  mcp-skills/                     CC̄=7.2    ←in:0  →out:0
  │ !! server                     639L  1C   12m  CC=15     ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  llm-agent/                      CC̄=4.0    ←in:0  →out:10  !! split
  │ !! agent_standalone           540L  3C   14m  CC=15     ←0
  │ agent                      375L  2C   13m  CC=4      ←0
  │ !! agent_git2mcp              361L  3C   13m  CC=15     ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  mcp-gateway/                    CC̄=3.5    ←in:0  →out:0
  │ server                     238L  2C   10m  CC=7      ←0
  │ default.yaml                14L  0C    0m  CC=0.0    ←0
  │ requirements.txt             7L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  dashboard/                      CC̄=3.2    ←in:0  →out:8  !! split
  │ server                     189L  2C   10m  CC=8      ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  git2mcp/                        CC̄=2.6    ←in:0  →out:0
  │ proxy                      437L  1C   21m  CC=12     ←0
  │ 05_local_iterate           126L  0C    1m  CC=5      ←0
  │ planfile.yaml              123L  0C    0m  CC=0.0    ←0
  │ 04_dry_run_vs_execute      115L  0C    2m  CC=3      ←0
  │ client                     104L  1C   20m  CC=4      ←0
  │ prefact.yaml                91L  0C    0m  CC=0.0    ←0
  │ 02_fragment_sync_to_skills    68L  0C    1m  CC=1      ←0
  │ 01_sync_and_commit          62L  0C    1m  CC=1      ←0
  │ pyproject.toml              57L  0C    0m  CC=0.0    ←0
  │ 03_agent_git2mcp            55L  0C    1m  CC=4      ←0
  │ generated-from-pytests.testql.toon.yaml    55L  0C    0m  CC=0.0    ←0
  │ prompt.txt                  49L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml          43L  0C    0m  CC=0.0    ←0
  │ evolution.toon.yaml         39L  0C    0m  CC=0.0    ←0
  │ project.toon.yaml           39L  0C    0m  CC=0.0    ←0
  │ map.toon.yaml               33L  0C    4m  CC=0.0    ←0
  │ calls.yaml                  29L  0C    0m  CC=0.0    ←0
  │ generated-api-integration.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ duplication.toon.yaml        9L  0C    0m  CC=0.0    ←0
  │ calls.toon.yaml              9L  0C    0m  CC=0.0    ←0
  │ client                       3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ proxy                        3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │
  mcp-webui/                      CC̄=2.2    ←in:0  →out:0
  │ server                     127L  0C    8m  CC=5      ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  mcp-git-proxy/                  CC̄=1.9    ←in:0  →out:0
  │ server                     298L  17C   20m  CC=3      ←0
  │ requirements.txt             4L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=0.0    ←in:26  →out:0
  │ test.sh                    397L  1C   14m  CC=0.0    ←9
  │ deploy.sh                  127L  0C    7m  CC=0.0    ←0
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ !! goal.yaml                  512L  0C    0m  CC=0.0    ←0
  │ docker-compose.yml         169L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ docker-compose.prod.yml     34L  0C    0m  CC=0.0    ←0
  │ tree.sh                      1L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     dashboard/Dockerfile                      0L
     llm-agent/Dockerfile                      0L
     mcp-gateway/Dockerfile                    0L
     mcp-git-proxy/Dockerfile                  0L
     mcp-skills/Dockerfile                     0L
     mcp-webui/Dockerfile                      0L

COUPLING:
                             scripts         llm-agent         dashboard  git2mcp.examples
           scripts                ──               ←10                ←8                ←8  hub
         llm-agent                10                ──                                      !! fan-out
         dashboard                 8                                  ──                    !! fan-out
  git2mcp.examples                 8                                                    ──  !! fan-out
  CYCLES: none
  HUB: scripts/ (fan-in=26)
  SMELL: git2mcp.examples/ fan-out=8 → split needed
  SMELL: llm-agent/ fan-out=10 → split needed
  SMELL: dashboard/ fan-out=8 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 4 groups | 19f 3746L | 2026-05-03

SUMMARY:
  files_scanned: 19
  total_lines:   3746
  dup_groups:    4
  dup_fragments: 10
  saved_lines:   61
  scan_ms:       6961

HOTSPOTS[3] (files with most duplication):
  llm-agent/agent.py  dup=41L  groups=2  frags=2  (1.1%)
  llm-agent/agent_standalone.py  dup=41L  groups=2  frags=2  (1.1%)
  mcp-git-proxy/server.py  dup=30L  groups=2  frags=6  (0.8%)

DUPLICATES[4] (ranked by impact):
  [aea4a7a9526a2ad3]   EXAC  _mock_llm_response  L=30 N=2 saved=30 sim=1.00
      llm-agent/agent.py:232-261  (_mock_llm_response)
      llm-agent/agent_standalone.py:405-434  (_mock_llm_response)
  [d7672c451ace4405]   STRU  worktree_diff  L=5 N=4 saved=15 sim=1.00
      mcp-git-proxy/server.py:213-217  (worktree_diff)
      mcp-git-proxy/server.py:229-233  (stage)
      mcp-git-proxy/server.py:237-241  (stash_save)
      mcp-git-proxy/server.py:261-265  (checkpoint_create)
  [5865906155183adc]   EXAC  _mock_llm_response_from_prompt  L=11 N=2 saved=11 sim=1.00
      llm-agent/agent.py:263-273  (_mock_llm_response_from_prompt)
      llm-agent/agent_standalone.py:436-446  (_mock_llm_response_from_prompt)
  [796eb26d67b6a889]   STRU  push  L=5 N=2 saved=5 sim=1.00
      mcp-git-proxy/server.py:179-183  (push)
      mcp-git-proxy/server.py:253-257  (branch_draft)

REFACTOR[4] (ranked by priority):
  [1] ○ extract_class      → llm-agent/utils/_mock_llm_response.py
      WHY: 2 occurrences of 30-line block across 2 files — saves 30 lines
      FILES: llm-agent/agent.py, llm-agent/agent_standalone.py
  [2] ○ extract_function   → mcp-git-proxy/utils/worktree_diff.py
      WHY: 4 occurrences of 5-line block across 1 files — saves 15 lines
      FILES: mcp-git-proxy/server.py
  [3] ○ extract_class      → llm-agent/utils/_mock_llm_response_from_prompt.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: llm-agent/agent.py, llm-agent/agent_standalone.py
  [4] ○ extract_function   → mcp-git-proxy/utils/push.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: mcp-git-proxy/server.py

QUICK_WINS[3] (low risk, high savings — do first):
  [1] extract_class      saved=30L  → llm-agent/utils/_mock_llm_response.py
      FILES: agent.py, agent_standalone.py
  [2] extract_function   saved=15L  → mcp-git-proxy/utils/worktree_diff.py
      FILES: server.py
  [3] extract_class      saved=11L  → llm-agent/utils/_mock_llm_response_from_prompt.py
      FILES: agent.py, agent_standalone.py

EFFORT_ESTIMATE (total ≈ 2.0h):
  medium _mock_llm_response                  saved=30L  ~60min
  medium worktree_diff                       saved=15L  ~30min
  easy   _mock_llm_response_from_prompt      saved=11L  ~22min
  easy   push                                saved=5L  ~10min

METRICS-TARGET:
  dup_groups:  4 → 0
  saved_lines: 61 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 145 func | 11f | 2026-05-03

NEXT[8] (ranked by impact):
  [1] !! SPLIT           mcp-skills/server.py
      WHY: 639L, 1 classes, max CC=15
      EFFORT: ~4h  IMPACT: 9585

  [2] !! SPLIT           llm-agent/agent_standalone.py
      WHY: 540L, 3 classes, max CC=15
      EFFORT: ~4h  IMPACT: 8100

  [3] !  SPLIT-FUNC      MCPSkillsServer._sync_from_git_proxy  CC=15  fan=30
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 450

  [4] !  SPLIT-FUNC      MCPSkillsServer._compute_metrics_for_repo  CC=15  fan=18
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 270

  [5] !  SPLIT-FUNC      LocalCodeAnalyzer.detect_code_patterns  CC=15  fan=15
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 225

  [6] !  SPLIT-FUNC      CachedCodeAnalyzer.compute_metrics  CC=15  fan=13
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 195

  [7] !  SPLIT-FUNC      MCPSkillsServer._recommend_refactoring  CC=15  fan=13
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 195

  [8] !  SPLIT-FUNC      LocalCodeAnalyzer.compute_metrics_for_repo  CC=15  fan=13
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 195


RISKS[2]:
  ⚠ Splitting mcp-skills/server.py may break 12 import paths
  ⚠ Splitting llm-agent/agent_standalone.py may break 14 import paths

METRICS-TARGET:
  CC̄:          3.4 → ≤2.4
  max-CC:      15 → ≤7
  god-modules: 2 → 0
  high-CC(≥15): 6 → ≤3
  hub-types:   0 → ≤0

PATTERNS (language parser shared logic):
  _extract_declarations() in base.py — unified extraction for:
    - TypeScript: interfaces, types, classes, functions, arrow funcs
    - PHP: namespaces, traits, classes, functions, includes
    - Ruby: modules, classes, methods, requires
    - C++: classes, structs, functions, #includes
    - C#: classes, interfaces, methods, usings
    - Java: classes, interfaces, methods, imports
    - Go: packages, functions, structs
    - Rust: modules, functions, traits, use statements

  Shared regex patterns per language:
    - import: language-specific import/require/using patterns
    - class: class/struct/trait declarations with inheritance
    - function: function/method signatures with visibility
    - brace_tracking: for C-family languages ({ })
    - end_keyword_tracking: for Ruby (module/class/def...end)

  Benefits:
    - Consistent extraction logic across all languages
    - Reduced code duplication (~70% reduction in parser LOC)
    - Easier maintenance: fix once, apply everywhere
    - Standardized FunctionInfo/ClassInfo models

HISTORY:
  (first run — no previous data)
```

## Intent

Autonomiczny Agent Refaktoryzacji MCP
