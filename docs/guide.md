# SteerCode — Hướng dẫn sử dụng

## SteerCode là gì?

SteerCode là công cụ Python phân tích codebase, xây dựng knowledge graph, và tạo steering files cho AI coding assistants. Không cần cài thêm thư viện — chỉ cần Python 3.7+.

**Vấn đề:** AI coding tools (Cursor, Copilot, Claude Code...) không hiểu kiến trúc project của bạn. Chúng viết code mà không biết file nào liên quan đến file nào, function nào gọi function nào.

**Giải pháp:** SteerCode scan codebase → tạo bản đồ → đưa cho AI đọc trước khi viết code.

```
Codebase → Scan → Parse → Semantic Analysis → Knowledge Graph
                                                    ↓
                                          Dashboard (cho người)
                                          Steering files (cho AI)
                                          Query engine (cho cả hai)
                                          MCP server (real-time)
```

---

## Cài đặt

```bash
git clone https://github.com/westermost/SteerCode.git
cd SteerCode
```

Không cần `pip install` — zero dependencies.

---

## Sử dụng cơ bản

### 1. Scan codebase

```bash
# Scan thư mục hiện tại
python steercode.py .

# Scan project cụ thể
python steercode.py /path/to/my-project

# Không mở browser
python steercode.py . --no-open
```

Kết quả:
- `.codemap-output/dashboard.html` — mở trong browser để xem graph
- `.kiro/steering/knowledge-graph.md` — Kiro tự đọc file này
- `.cursor/rules/knowledge-graph.md` — Cursor tự đọc file này
- `.github/copilot-instructions.md` — Copilot tự đọc file này

### 2. Interactive wizard

```bash
# Chạy không có argument → wizard hỏi từng bước
python steercode.py
```

Wizard hỏi: đường dẫn project, có dùng LLM không, output ở đâu, tạo steering cho tool nào. Settings lưu vào `~/.steercode.json` cho lần sau.

### 3. Chỉ tạo steering cho tool cụ thể

```bash
python steercode.py . --tools kiro,cursor
python steercode.py . --tools claude,copilot
```

---

## Dùng với Local LLM

Kết nối LM Studio hoặc Ollama để AI viết summary cho mỗi function/class:

```bash
# LM Studio (port mặc định 1234)
python steercode.py . --llm http://localhost:1234

# Ollama
python steercode.py . --llm http://localhost:11434

# Chọn model + context size
python steercode.py . --llm http://localhost:1234 --model qwen2.5-coder --context-size 8192

# Giới hạn số nodes enrich (tiết kiệm thời gian)
python steercode.py . --llm http://localhost:1234 --max-enrich 50
```

**Không có LLM vẫn hoạt động** — SteerCode tự phân tích semantic (side effects, domain, role) bằng regex, không cần LLM.

**Có LLM thì tốt hơn** — mỗi function/class có summary bằng tiếng Anh mô tả behavior.

### LLM hoạt động thế nào?

1. Parse code trước (deterministic) → extract metadata
2. Gửi metadata + code snippet cho LLM theo batch (10-20 files/batch)
3. Format: `<FUNC id="f0" domain="payment" role="orchestrator">...</FUNC>`
4. LLM chỉ viết summary, không cần parse code
5. Validate response → retry nếu thiếu IDs
6. Cache kết quả → lần chạy sau skip batches đã xong

---

## Incremental (chạy lại nhanh)

```bash
python steercode.py .          # Lần 1: full scan (~10s cho project 500 files)
# ... sửa vài files ...
python steercode.py .          # Lần 2: phát hiện không đổi → skip ngay
python steercode.py . --full   # Bắt buộc scan lại toàn bộ
```

SteerCode lưu fingerprint (MD5) của mỗi file. Lần chạy sau so sánh → chỉ xử lý files thay đổi.

Lưu ý: Nếu lần 1 chạy không LLM, lần 2 thêm `--llm` thì vẫn chạy bình thường (không bị skip). Batch cache sẽ tự skip các batches đã enrich rồi.

---

## Query Engine

Sau khi scan xong, query knowledge graph từ CLI:

### Tìm functions theo side effect

```bash
# Functions nào gọi external API?
python steercode.py query find --effect external_api

# Functions nào ghi database?
python steercode.py query find --effect db_write

# Functions thuộc domain payment?
python steercode.py query find --domain payment

# Tìm theo tên
python steercode.py query find --name login
```

### Impact analysis

```bash
# Nếu sửa processPayment, cái gì bị ảnh hưởng?
python steercode.py query impact processPayment
```

### Trace execution flow

```bash
# Đường đi từ CartController đến StripeGateway?
python steercode.py query flow CartController StripeGateway
```

### Xem chi tiết function

```bash
python steercode.py query explain processPayment
```

Output:
```json
{
  "name": "processPayment",
  "type": "function",
  "file": "src/services/PaymentService.php",
  "summary": "Handles checkout flow via Stripe API",
  "complexity": "complex",
  "domain": "payment",
  "role": "orchestrator",
  "effects": ["external_api:stripe", "db_write:transactions"],
  "callers": ["OrderController", "CartController"],
  "callees": ["validateAmount", "stripeCharge", "saveTransaction"]
}
```

---

## MCP Server

Cho phép AI tools query knowledge graph real-time:

### Cấu hình cho Kiro / Cursor / Claude Code

Thêm vào MCP config của tool:

```json
{
  "mcpServers": {
    "steercode": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

AI tool sẽ có 4 tools mới:
- `steercode_find` — tìm functions theo domain/effect/role
- `steercode_impact` — phân tích ảnh hưởng khi sửa code
- `steercode_flow` — trace execution path
- `steercode_explain` — xem chi tiết function

### Test MCP server

```bash
cd /path/to/your/project
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python -m src.mcp_server
```

---

## Dashboard

Mở `.codemap-output/dashboard.html` trong browser:

- **Kéo thả** nodes, zoom in/out
- **Click node** → xem chi tiết (summary, connections, complexity)
- **Ctrl+K** → search
- **Filter** theo layer (API, Service, Data...), type (file, function, class), complexity, language
- **Click-to-expand** — graph lớn chỉ load connections khi click
- **5 ngôn ngữ** — English, 한국어, 中文, 日本語, Español

---

## Semantic Analysis

SteerCode tự phân tích mỗi function/class (không cần LLM):

| Tín hiệu | Ví dụ | Cách detect |
|---|---|---|
| Side effects | `db_write:transactions`, `external_api:stripe` | Regex + import inference |
| Business domain | `payment`, `auth`, `user` | Keyword matching |
| Execution role | `orchestrator`, `entry_point`, `validator` | Name + path patterns |
| Control flow | `branching`, `loop`, `try_catch`, `async` | Pattern detection |
| Importance | 0.0 → 1.0 | Callers + effects + role → percentile |

---

## Ngôn ngữ hỗ trợ

**Full AST parsing:** Python

**Regex parsing:** JavaScript, TypeScript, Java, Go, Rust, C/C++, C#, Ruby, PHP, Kotlin, Swift, Scala, Lua, Shell

**Detect (không parse):** JSON, YAML, TOML, HTML, CSS, SQL, Markdown, Dockerfile, Terraform, Protobuf, GraphQL, Vue, Twig, Blade

---

## AI Tools hỗ trợ

| Tool | File | Tự động? |
|---|---|---|
| Kiro | `.kiro/steering/knowledge-graph.md` | ✅ |
| Cursor | `.cursor/rules/knowledge-graph.md` | ✅ |
| GitHub Copilot | `.github/copilot-instructions.md` | ✅ |
| Claude Code | `.codemap-output/steering/CLAUDE.md` | Copy về root |
| Windsurf | `.codemap-output/steering/.windsurfrules` | Copy về root |
| Cline | `.codemap-output/steering/.clinerules` | Copy về root |
| Codex | `.codemap-output/steering/AGENTS.md` | Copy về root |

---

## Hiệu năng (Performance)

SteerCode được tối ưu cho codebase lớn (50K+ files):

| Thao tác | Project nhỏ (100 files) | Project lớn (20K files) |
|---|---|---|
| Scan files | ~0.1s | ~2s |
| Fingerprint | ~0.01s | ~0.5s |
| Parse + build graph | ~0.5s | ~30s |
| Semantic extraction | ~0.1s | ~3s |
| Importance scoring | ~0.01s | ~0.2s |
| LLM enrichment | ~2 min | ~30 min (concurrent) |
| Incremental (no change) | instant | instant |

Các tối ưu chính:
- Semantic extraction chạy 1 lần per file (không per function)
- Fingerprint dùng size+mtime (không đọc file content)
- Importance scoring dùng adjacency map O(N+E)
- Scan progress throttle mỗi 50 files (tránh I/O bottleneck)
- LLM batch cache — lần chạy sau skip batches đã xong
- Khi thêm `--llm` vào lần chạy sau, không bị skip bởi incremental

---

## Tất cả CLI options

```
python steercode.py [path] [options]
python steercode.py query <command> [args]

Scan:
  -o, --output DIR       Thư mục output (mặc định: .codemap-output)
  --llm URL              URL local LLM
  --model NAME           Tên model (tùy chọn)
  --context-size N       Context size (mặc định: 8192)
  --max-enrich N         Giới hạn số nodes enrich
  --tools LIST           AI tools (kiro,cursor,copilot,claude,windsurf,cline,codex)
  --no-open              Không mở browser
  --json-only            Chỉ xuất JSON
  --full                 Bắt buộc scan lại toàn bộ

Query:
  query find [--type T] [--domain D] [--effect E] [--name N]
  query impact <tên_function>
  query flow <từ> <đến>
  query explain <tên_function>
```

---

## Ví dụ thực tế

### Project PHP (Laravel)

```bash
cd ~/projects/my-laravel-app
python ~/SteerCode/steercode.py . --llm http://localhost:1234

# Xem functions nào ghi DB
python ~/SteerCode/steercode.py query find --effect db_write

# Sửa UserController → cái gì bị ảnh hưởng?
python ~/SteerCode/steercode.py query impact UserController
```

### Project TypeScript (Next.js)

```bash
cd ~/projects/my-nextjs-app
python ~/SteerCode/steercode.py . --tools kiro,cursor

# Cursor sẽ tự đọc .cursor/rules/knowledge-graph.md
# Kiro sẽ tự đọc .kiro/steering/knowledge-graph.md
```

### Project lớn (50K+ files)

```bash
python steercode.py . --no-open --json-only
# → graph-index.json (~2K tokens) + layers/*.json
# AI load từng layer thay vì toàn bộ graph
```
