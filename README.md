# MiniLang Studio

MiniLang Studio, Sistem Programlama dersi final projesi için geliştirilmiş el yapımı (hand-coded) iki geçişli bir derleyici uygulamasıdır. Projede Pass 1 (Lexer) kaynak kodu token'lara ayırır, Pass 2 (Parser + Semantic Analyzer) sözdizimi/anlam kontrolü yapar, sembol tablosunu yönetir, AST ve TAC üretir. Arayüz web tabanlıdır ve Token Stream, Line Mapping, Symbol Table, AST, TAC ve Error Log panellerini gösterir.

## Proje Dosyaları

- `lexer.py` — Pass 1 (Lexical Analysis)
- `parser.py` — Pass 2 (Syntax + Semantic Analysis)
- `symbol_table.py` — Symbol Table yönetimi
- `app.py` — Web sunucu + derleyici entegrasyonu
- `studio_ui.html` — Arayüz (IDE görünümü)
- `examples/sample_program.ml` — Örnek MiniLang programı

## Çalıştırma (Sırayla)

```bash
cd /Users/nursenakay/Desktop/MiniLang_Compiler
python3 app.py
```

Ardından tarayıcıdan açın:

```text
http://127.0.0.1:8765
```

Port doluysa önce çalışan süreci kapatın:

```bash
lsof -ti:8765 | xargs kill -9
python3 app.py
```
