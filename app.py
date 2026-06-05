"""
MiniLang Studio — Web Arayüzü
=============================
Python standart kütüphanesi (http.server) ile tarayıcı tabanlı IDE.
Ek paket veya tkinter GEREKMEZ — Homebrew Python ile doğrudan çalışır.

Çalıştırma:
    python3 app.py

Tarayıcıda otomatik açılır: http://127.0.0.1:8765
Durdurmak için: Ctrl+C
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from lexer import Lexer, Token
from parser import Parser

PROJECT_DIR = Path(__file__).parent
EXAMPLES_DIR = PROJECT_DIR / "examples"
SAMPLE_FILE = EXAMPLES_DIR / "sample_program.ml"


# ------------------------------------------------------------------ #
#  Three-Address Code (TAC)
# ------------------------------------------------------------------ #

class TACGenerator:
    """Parser AST'sinden üç adresli kod üretir."""

    def __init__(self) -> None:
        self.instructions: list[str] = []
        self._temp_counter = 0

    def _new_temp(self) -> str:
        self._temp_counter += 1
        return f"t{self._temp_counter}"

    def generate(self, ast: dict | None) -> list[str]:
      self.instructions = []
      self._temp_counter = 0
      if ast is None:
        return []
      for stmt in ast.get("statements", []):
        self._gen_statement(stmt)
      return self.instructions

    def _emit(self, instruction: str) -> None:
        self.instructions.append(instruction)

    def _gen_statement(self, node: dict | None) -> None:
        if node is None:
            return
        ntype = node.get("type")

        if ntype == "VarDecl":
            name = node.get("name", "?")
            if node.get("initializer"):
                value = self._gen_expression(node["initializer"])
                if value:
                    self._emit(f"{name} = {value}")
            else:
                self._emit(f"declare {node.get('var_type')} {name}")

        elif ntype == "Assign":
            value = self._gen_expression(node.get("value"))
            if value:
                self._emit(f"{node.get('name')} = {value}")

        elif ntype == "PrintStmt":
            arg = self._gen_expression(node.get("argument"))
            if arg:
                self._emit(f"print {arg}")

        elif ntype == "IfStmt":
            cond = self._gen_expression(node.get("condition"))
            if cond:
                l_false = f"L_false_{len(self.instructions)}"
                l_end = f"L_end_{len(self.instructions)}"
                self._emit(f"ifFalse {cond} goto {l_false}")
                self._gen_block(node.get("then_branch"))
                self._emit(f"goto {l_end}")
                self._emit(f"{l_false}:")
                if node.get("else_branch"):
                    self._gen_block(node.get("else_branch"))
                self._emit(f"{l_end}:")

        elif ntype == "WhileStmt":
            l_start = f"L_while_{len(self.instructions)}"
            l_end = f"L_end_while_{len(self.instructions)}"
            self._emit(f"{l_start}:")
            cond = self._gen_expression(node.get("condition"))
            if cond:
                self._emit(f"ifFalse {cond} goto {l_end}")
            self._gen_block(node.get("body"))
            self._emit(f"goto {l_start}")
            self._emit(f"{l_end}:")

        elif ntype == "Block":
            self._gen_block(node)

    def _gen_block(self, block: dict | None) -> None:
        if block is None:
            return
        for stmt in block.get("statements", []):
            self._gen_statement(stmt)

    def _gen_expression(self, node: dict | None) -> str | None:
        if node is None:
            return None
        ntype = node.get("type")
        if ntype == "Literal":
            return node.get("value")
        if ntype == "Identifier":
            return node.get("name")
        if ntype == "BinaryOp":
            left = self._gen_expression(node.get("left"))
            right = self._gen_expression(node.get("right"))
            if left is None or right is None:
                return None
            temp = self._new_temp()
            op = node.get("operator", "?")
            self._emit(f"{temp} = {left} {op} {right}")
            return temp
        return None


# ------------------------------------------------------------------ #
#  Derleyici motoru
# ------------------------------------------------------------------ #

def build_line_mapping(source: str, tokens: list[dict]) -> list[dict]:
    """
    Kaynak kodun her satırını ilgili token'larla eşleştirir (PDF UI şartı).
    """
    lines = source.splitlines()
    max_token_line = max((t["line"] for t in tokens), default=0)
    total = max(len(lines), max_token_line)

    mapping: list[dict] = []
    for line_no in range(1, total + 1):
        source_line = lines[line_no - 1] if line_no <= len(lines) else ""
        line_tokens = [t for t in tokens if t["line"] == line_no]
        summary = (
            " | ".join(f"{t['type']}({t['value']})" for t in line_tokens)
            if line_tokens
            else "(boş satır / yorum)"
        )
        mapping.append(
            {
                "line": line_no,
                "source": source_line,
                "tokens": line_tokens,
                "token_summary": summary,
            }
        )
    return mapping


def read_source_file(path: Path) -> str:
    """Kaynak kodu dosyadan okur."""
    return path.read_text(encoding="utf-8")


def run_compiler(source: str) -> dict:
    """Kaynak kodu analiz eder; JSON'a uygun sonuç döndürür."""
    lexer = Lexer(source)
    tokens: list[Token] = lexer.tokenize()

    # Pass 1 sembol tablosu anlık görüntüsü
    symbols_pass1 = [s.to_dict() for s in lexer.symbol_table.all_symbols()]

    token_dicts = [
        {"line": t.line, "type": t.token_type, "value": t.value}
        for t in tokens
    ]

    parser = Parser(tokens, symbol_table=lexer.symbol_table)
    ast = parser.parse()
    tac = TACGenerator().generate(ast)

    errors: list[str] = []
    errors.extend(lexer.errors)
    errors.extend(parser.errors)

    return {
        "tokens": token_dicts,
        "symbols_pass1": symbols_pass1,
        "symbols": [s.to_dict() for s in parser.symbol_table.all_symbols()],
        "line_mapping": build_line_mapping(source, token_dicts),
        "ast_json": parser.to_json() if ast else "",
        "tac": tac,
        "errors": errors,
    }


# ------------------------------------------------------------------ #
#  HTML arayüz (studio_ui.html)
# ------------------------------------------------------------------ #

UI_FILE = PROJECT_DIR / "studio_ui.html"


def load_ui_page() -> str:
    return UI_FILE.read_text(encoding="utf-8")


# Eski gömülü şablon kaldırıldı — studio_ui.html kullanılır
_LEGACY_HTML_REMOVED = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MiniLang Studio — Two-Pass Compiler</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif;
      background: #1e1e2e;
      color: #cdd6f4;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      padding: 12px 16px;
      display: flex;
      align-items: center;
      gap: 16px;
      border-bottom: 1px solid #313244;
    }
    #analyze-btn {
      background: #89b4fa;
      color: #1e1e2e;
      border: none;
      padding: 12px 28px;
      font-size: 15px;
      font-weight: 700;
      border-radius: 8px;
      cursor: pointer;
    }
    #analyze-btn:hover { background: #b4befe; }
    #analyze-btn:disabled { opacity: 0.6; cursor: wait; }
    .subtitle { color: #a6adc8; font-size: 13px; }
    .toolbar { display: flex; gap: 8px; padding: 8px 14px; background: #2a2a3d; border-bottom: 1px solid #313244; flex-wrap: wrap; }
    .toolbar button, .toolbar label {
      font-size: 12px; padding: 6px 12px; border-radius: 6px; cursor: pointer;
      background: #45475a; color: #cdd6f4; border: none;
    }
    .toolbar label:hover, .toolbar button:hover { background: #585b70; }
    .section-label { font-size: 11px; color: #a6adc8; padding: 8px 12px 4px; }
    .mapping-source { color: #89b4fa; max-width: 40%; }
    .mapping-tokens { color: #a6e3a1; font-size: 11px; }
    main {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0;
      min-height: 0;
    }
    .panel {
      display: flex;
      flex-direction: column;
      border-right: 1px solid #313244;
      min-height: 0;
    }
    .panel:last-child { border-right: none; }
    .panel-title {
      padding: 10px 14px;
      font-weight: 600;
      color: #89b4fa;
      font-size: 13px;
      background: #2a2a3d;
      border-bottom: 1px solid #313244;
    }
    #source-code {
      flex: 1;
      width: 100%;
      border: none;
      background: #1a1b26;
      color: #cdd6f4;
      font-family: Menlo, Monaco, "Courier New", monospace;
      font-size: 13px;
      line-height: 1.5;
      padding: 14px;
      resize: none;
      outline: none;
    }
    .tabs {
      display: flex;
      background: #2a2a3d;
      border-bottom: 1px solid #313244;
    }
    .tab {
      padding: 10px 16px;
      cursor: pointer;
      font-size: 13px;
      color: #a6adc8;
      border: none;
      background: transparent;
    }
    .tab.active {
      color: #1e1e2e;
      background: #89b4fa;
      font-weight: 600;
    }
    .tab-content {
      flex: 1;
      overflow: auto;
      display: none;
      min-height: 0;
    }
    .tab-content.active { display: block; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th {
      position: sticky;
      top: 0;
      background: #45475a;
      color: #89b4fa;
      text-align: left;
      padding: 8px 12px;
    }
    td {
      padding: 6px 12px;
      border-bottom: 1px solid #313244;
      font-family: Menlo, monospace;
    }
    tr:hover td { background: #313244; }
    pre.code-view {
      margin: 0;
      padding: 14px;
      font-family: Menlo, Monaco, monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre;
      color: #cdd6f4;
    }
    pre.tac-view { color: #a6e3a1; }
    footer {
      border-top: 1px solid #585b70;
      background: #2d1515;
      min-height: 120px;
      max-height: 180px;
      display: flex;
      flex-direction: column;
    }
    footer .panel-title { color: #f38ba8; background: #2d1515; }
    #error-log {
      flex: 1;
      overflow: auto;
      padding: 10px 14px;
      font-family: Menlo, monospace;
      font-size: 12px;
      color: #f38ba8;
      white-space: pre-wrap;
    }
    .ok { color: #a6e3a1; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <button id="analyze-btn">&#9654; Analyze Code</button>
    <span class="subtitle">Lexer &rarr; Parser &rarr; AST / TAC &nbsp;|&nbsp; Hand-Coded MiniLang</span>
  </header>

  <main>
    <section class="panel">
      <div class="panel-title">Source Code</div>
      <div class="toolbar">
        <button type="button" id="load-sample-btn">&#128196; PDF Örnek Program</button>
      </div>
      <textarea id="source-code" spellcheck="false"></textarea>
    </section>

    <section class="panel">
      <div class="tabs">
        <button class="tab active" data-tab="tokens">Token Stream</button>
        <button class="tab" data-tab="mapping">Line Mapping</button>
        <button class="tab" data-tab="symbols">Symbol Table</button>
        <button class="tab" data-tab="ast">AST (JSON)</button>
        <button class="tab" data-tab="tac">TAC</button>
      </div>
      <div id="tab-tokens" class="tab-content active">
        <table>
          <thead><tr><th>Line</th><th>Token Type</th><th>Value</th></tr></thead>
          <tbody id="token-body"></tbody>
        </table>
      </div>
      <div id="tab-mapping" class="tab-content">
        <table>
          <thead><tr><th>Line</th><th>Source</th><th>Tokens</th></tr></thead>
          <tbody id="mapping-body"></tbody>
        </table>
      </div>
      <div id="tab-symbols" class="tab-content">
        <div class="section-label">Pass 1 — Lexer (tanımlayıcılar, tip henüz ?)</div>
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Memory</th><th>Scope</th></tr></thead>
          <tbody id="symbol-pass1-body"></tbody>
        </table>
        <div class="section-label">Pass 2 — Parser (tam tip ve bellek adresi)</div>
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Memory</th><th>Scope</th></tr></thead>
          <tbody id="symbol-body"></tbody>
        </table>
      </div>
      <div id="tab-ast" class="tab-content">
        <pre id="ast-view" class="code-view">(Run Analyze Code)</pre>
      </div>
      <div id="tab-tac" class="tab-content">
        <pre id="tac-view" class="code-view tac-view">(Run Analyze Code)</pre>
      </div>
    </section>
  </main>

  <footer>
    <div class="panel-title">Error Log (Lexical &middot; Syntax &middot; Semantic)</div>
    <div id="error-log">Ready.</div>
  </footer>

  <script>
    const DEFAULT_SOURCE = `int x = 10;
float y = 3.14;
int z = x + 2 * 3;

if (x > 5 && y != 0.0) {
    print("Result is large");
} else {
    x = x + 1;
}

while (x < 20) {
    x = x + 1;
}`;

    document.getElementById("source-code").value = DEFAULT_SOURCE;

    document.getElementById("load-sample-btn").addEventListener("click", async () => {
      try {
        const res = await fetch("/api/sample");
        const data = await res.json();
        document.getElementById("source-code").value = data.source || "";
      } catch (err) {
        alert("Örnek dosya yüklenemedi: " + err.message);
      }
    });

    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
      });
    });

    function fillTable(tbodyId, rows, cols) {
      const tbody = document.getElementById(tbodyId);
      tbody.innerHTML = "";
      if (!rows.length) {
        tbody.innerHTML = "<tr><td colspan='" + cols + "' style='color:#6c7086'>—</td></tr>";
        return;
      }
      rows.forEach(row => {
        const tr = document.createElement("tr");
        row.forEach(cell => {
          const td = document.createElement("td");
          td.textContent = cell;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }

    async function analyze() {
      const btn = document.getElementById("analyze-btn");
      const source = document.getElementById("source-code").value;
      btn.disabled = true;
      btn.textContent = "Analyzing…";

      try {
        const res = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source })
        });
        const data = await res.json();

        fillTable("token-body",
          data.tokens.map(t => [t.line, t.type, t.value]), 3);

        fillTable("mapping-body",
          (data.line_mapping || []).map(m => [
            m.line,
            m.source || "(boş)",
            m.token_summary
          ]), 3);

        fillTable("symbol-pass1-body",
          (data.symbols_pass1 || []).map(s => [s.name, s.type, s.memory_location, s.scope]), 4);

        fillTable("symbol-body",
          data.symbols.map(s => [s.name, s.type, s.memory_location, s.scope]), 4);

        document.getElementById("ast-view").textContent =
          data.ast_json || "(No AST — fix errors below)";
        document.getElementById("tac-view").textContent =
          data.tac.length ? data.tac.join("\\n") : "(No TAC generated)";

        const log = document.getElementById("error-log");
        if (data.errors.length) {
          log.className = "";
          log.textContent = data.errors.map(e => "✗  " + e).join("\\n");
        } else {
          log.className = "ok";
          log.textContent = "✓  No errors found. Analysis completed successfully.";
          document.querySelector('[data-tab="ast"]').click();
        }
      } catch (err) {
        document.getElementById("error-log").textContent = "✗  " + err.message;
      } finally {
        btn.disabled = false;
        btn.innerHTML = "&#9654; Analyze Code";
      }
    }

    document.getElementById("analyze-btn").addEventListener("click", analyze);
  </script>
</body>
</html>
"""


# ------------------------------------------------------------------ #
#  HTTP sunucusu
# ------------------------------------------------------------------ #

HOST = "127.0.0.1"
PORT = 8765


class CompilerHTTPRequestHandler(BaseHTTPRequestHandler):
    """Ana sayfa ve /api/analyze uç noktalarını sunar."""

    def log_message(self, format: str, *args) -> None:
        # Sadece analyze isteklerini göster (sayfa yenilemelerini gizle)
        if args and "analyze" in str(args[0]):
            print(f"[{self.log_date_time_string()}] {format % args}")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html(load_ui_page())
        elif path == "/api/sample":
            try:
                source = read_source_file(SAMPLE_FILE)
                self._send_json(200, {"source": source, "filename": SAMPLE_FILE.name})
            except FileNotFoundError:
                self._send_json(404, {"errors": ["sample_program.ml not found"]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/analyze":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")

        try:
            data = json.loads(raw) if raw else {}
            source = data.get("source", "")
            result = run_compiler(source)
            self._send_json(200, result)
        except json.JSONDecodeError:
            self._send_json(400, {"errors": ["Invalid JSON body"]})
        except Exception as exc:
            self._send_json(500, {"errors": [f"Internal Error: {exc}"]})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()


def main() -> None:
    server = HTTPServer((HOST, PORT), CompilerHTTPRequestHandler)
    url = f"http://{HOST}:{PORT}"

    print("=" * 50)
    print("  MiniLang Studio — Web UI")
    print("=" * 50)
    print(f"  Sunucu: {url}")
    print("  Durdurmak için: Ctrl+C")
    print("=" * 50)

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatıldı.")
        server.server_close()


if __name__ == "__main__":
    main()
