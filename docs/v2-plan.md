# SteerCode v2.0 — Feature Plan

6 tính năng mới học từ Understand-Anything, xếp theo thứ tự implement.

---

## 1. Diff Analysis — `steercode diff`

**Mục tiêu:** Trước khi commit, biết code thay đổi ảnh hưởng gì.

```bash
steercode diff                    # staged changes
steercode diff HEAD~3             # last 3 commits
steercode diff main..feature      # branch comparison
```

**Output:**
```
Changed: 3 files, 5 functions
Affected: 12 nodes across 3 layers (Service, Data, API)
Risk: HIGH — touches PaymentService (orchestrator, external_api:stripe)

Changed:
  ✎ processPayment (Service) — orchestrator, external_api:stripe
  ✎ validateAmount (Service) — validator

Affected (1-hop):
  → OrderController (API) — calls processPayment
  → TransactionRepo (Data) — called by processPayment
  → refundPayment (Service) — shares StripeGateway dependency
```

**Implementation:**
- `src/diff.py` — `get_changed_files(ref)` via `git diff --name-only`
- Map changed files → graph nodes via `file_id_map`
- Expand "contains" edges → get changed functions/classes
- Expand 1-hop "calls"/"imports" → affected nodes
- Risk scoring: HIGH if touches orchestrator/external_api, MEDIUM if data_access, LOW otherwise
- `steercode.py` — add `diff` subcommand
- Không cần LLM

**Files:** `src/diff.py` (new), `steercode.py`

---

## 2. Onboarding Guide — `steercode onboard`

**Mục tiêu:** Tạo docs/ONBOARDING.md cho dev mới join team.

```bash
steercode onboard                 # generate from graph
steercode onboard --llm URL       # with LLM for richer descriptions
```

**Output:** `docs/ONBOARDING.md`
```markdown
# Project: homes-pc

## Overview
| Metric | Value |
|---|---|
| Languages | PHP, JavaScript, YAML |
| Files | 20,733 |
| Functions | 27,458 |
| Frameworks | Symfony 2.0.4 |

## Architecture
- **API / Routes** (1,234 nodes) — Controllers, route handlers
- **Service / Logic** (8,456 nodes) — Business logic, orchestrators
- **Data / Storage** (3,211 nodes) — Models, repositories, migrations

## Key Components
1. `PaymentService` — orchestrator, [payment], → external_api:stripe, db_write
2. `AuthController` — entry_point, [auth], → db_read
...top 20 by importance

## Complexity Hotspots
1. `LegacyOrderProcessor` (complex, 450 lines) — Service
2. `ReportGenerator` (complex, 380 lines) — Service

## Getting Started
Recommended reading order (by dependency):
1. src/Entity/ — Data models
2. src/Repository/ — Data access
3. src/Service/ — Business logic
4. src/Controller/ — API endpoints
```

**Implementation:**
- `src/onboard.py` — `generate_onboard(graph_data, root, llm_fn=None)`
- Dùng data đã có: layers, importance scores, complexity, semantics
- Optional LLM: enrich section descriptions
- `steercode.py` — add `onboard` subcommand

**Files:** `src/onboard.py` (new), `steercode.py`

---

## 3. Explain with Source — `steercode explain`

**Mục tiêu:** Deep-dive vào 1 function/file, xem source + context + giải thích.

```bash
steercode explain processPayment
steercode explain src/services/PaymentService.php
steercode explain src/services/PaymentService.php:processPayment
```

**Output:**
```
═══ processPayment ═══
File: src/services/PaymentService.php (lines 45-120)
Type: function | Layer: Service | Domain: payment | Role: orchestrator
Complexity: complex | Importance: 0.95

Side effects: external_api:stripe, db_write:transactions
Control flow: try_catch, branching, async

Called by:
  → OrderController.placeOrder (API, entry_point)
  → CartController.checkout (API, entry_point)

Calls:
  → validateAmount (validator)
  → stripeCharge (adapter, external_api:stripe)
  → saveTransaction (data_access, db_write)

Source:
  45 │ public function processPayment($userId, $amount, $currency) {
  46 │     $this->validateAmount($amount);
  ...
 120 │ }

Summary: Handles full checkout flow via Stripe — validates amount,
charges card, persists transaction. Central orchestrator for payment domain.
```

**Implementation:**
- Enhance `src/query.py` `explain()` — add source code reading + formatting
- `steercode.py` — add `explain` subcommand (separate from `query explain`)
- Nếu có LLM: generate summary on-the-fly cho nodes chưa có summary
- Nếu không LLM: dùng auto-summary từ semantics

**Files:** `src/query.py` (modify), `steercode.py`

---

## 4. Chat Mode — `steercode chat`

**Mục tiêu:** Hỏi tự do về codebase, trả lời bằng graph context.

```bash
steercode chat --llm http://localhost:1234
> how does authentication work?
> what happens if I change the User model?
> which functions touch the database?
```

**Flow:**
```
User question
  → Search graph (fuzzy match keywords in names/summaries/tags)
  → Expand 1-hop edges → collect relevant subgraph
  → Build context: nodes + relationships + layer info
  → Send context + question to LLM
  → Print answer
```

**Implementation:**
- `src/chat.py` — `ChatSession(graph_path, llm_url, model)`
  - `search(query)` → dùng `GraphQuery.find()` + fuzzy name matching
  - `build_context(nodes)` → format subgraph as markdown
  - `ask(question)` → search + context + LLM → answer
- Interactive REPL loop với history
- `steercode.py` — add `chat` subcommand
- **Cần LLM** — không có LLM thì chỉ trả danh sách nodes

**Files:** `src/chat.py` (new), `steercode.py`

---

## 5. Domain Graph — `steercode domain`

**Mục tiêu:** Extract business flows từ code, tạo domain-graph.json.

```bash
steercode domain --llm http://localhost:1234
```

**Output:** `.codemap-output/domain-graph.json`
```json
{
  "domains": [
    {
      "name": "Payment",
      "description": "Handles checkout, billing, refunds",
      "flows": [
        {
          "name": "Checkout Flow",
          "steps": [
            {"name": "Validate cart", "node": "CartValidator"},
            {"name": "Process payment", "node": "PaymentService.processPayment"},
            {"name": "Create order", "node": "OrderService.createOrder"},
            {"name": "Send confirmation", "node": "EmailService.sendOrderConfirmation"}
          ]
        }
      ]
    }
  ]
}
```

**Implementation:**
- `src/domain.py` — `extract_domains(graph_data, llm_url, model)`
  - Group nodes by `domain_hint` (đã có từ semantic extraction)
  - Trong mỗi domain, trace call chains từ entry_points → data_access
  - Gửi chains cho LLM → LLM đặt tên flow + mô tả steps
- `steercode.py` — add `domain` subcommand
- **Cần LLM** — để đặt tên flows và mô tả steps

**Files:** `src/domain.py` (new), `steercode.py`

---

## 6. Guided Tours — `steercode tour`

**Mục tiêu:** Tạo learning path cho codebase, ordered by dependency.

```bash
steercode tour                    # auto-generate
steercode tour --focus payment    # focus on payment domain
```

**Output:**
```
═══ Guided Tour: homes-pc ═══

Stop 1/8: Data Models (src/Entity/)
  Start here — these define the core data structures.
  Key files: User.php, Order.php, Product.php
  Concepts: Doctrine ORM, entity relationships

Stop 2/8: Repositories (src/Repository/)
  Data access layer — how models are queried and persisted.
  Key files: UserRepository.php, OrderRepository.php
  Depends on: Stop 1 (entities)

Stop 3/8: Services (src/Service/)
  Business logic — orchestrates data access + external APIs.
  Key files: PaymentService.php, OrderService.php
  Depends on: Stop 1, 2

...
```

**Implementation:**
- `src/tour.py` — `generate_tour(graph_data, focus_domain=None)`
  - Topological sort layers by dependency (Data → Service → API)
  - Trong mỗi layer, sort by importance
  - Group by directory → tạo "stops"
  - Optional LLM: enrich stop descriptions
- `steercode.py` — add `tour` subcommand
- Không bắt buộc LLM — dùng layer + importance + semantics đã có

**Files:** `src/tour.py` (new), `steercode.py`

---

## Execution Order

```
Phase 1 (no LLM needed):
  #1 Diff Analysis      ← daily use, highest value
  #2 Onboarding Guide   ← one-time but very useful
  #3 Explain with Source ← enhance existing feature

Phase 2 (needs LLM):
  #4 Chat Mode          ← interactive, needs LLM
  #6 Guided Tours       ← works without LLM too

Phase 3 (needs LLM + complex):
  #5 Domain Graph       ← most complex, highest LLM dependency
```

## CLI sau khi hoàn thành

```bash
steercode .                       # scan + dashboard + steering
steercode diff                    # impact analysis on git changes
steercode onboard                 # generate onboarding guide
steercode explain <name>          # deep-dive with source
steercode chat --llm URL          # interactive Q&A
steercode tour                    # guided learning path
steercode domain --llm URL        # extract business flows
steercode query find/impact/flow  # programmatic queries
```
