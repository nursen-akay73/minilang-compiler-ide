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

---

## Hata Türleri (Lexical · Syntax · Semantic)

Final proje dokümanı (§7) en az **3 farklı hata türünün** satır numarasıyla birlikte raporlanmasını zorunlu kılar. MiniLang Studio bu üç aşamada hataları yakalar ve **Error Log** panelinde gösterir.

| Aşama | Hata türü | Kim yakalar? | Ne zaman oluşur? |
|-------|-----------|--------------|------------------|
| Pass 1 | **Lexical** | Lexer | Geçersiz karakter, bozuk sayı, kapanmamış string/yorum |
| Pass 2 | **Syntax** | Parser | BNF kurallarına uymayan yapı (eksik `;`, yanlış token sırası) |
| Pass 2 | **Semantic** | Semantic Analyzer | Tanımsız değişken, tekrar tanım, tip uyuşmazlığı |

Sunumda bu üç türü sırayla göstermek için aşağıdaki kısa kodları editöre yapıştırıp **Analyze Code**'a basmanız yeterlidir.

### 1. Lexical Error (Sözcük Analizi Hatası)

**Örnek kod** — dilde tanımlı olmayan `@` karakteri:

```minilang
int x = 10;
int y = @5;
```

**Neden hata?** Pass 1 (Lexer) kaynak kodu karakter karakter tararken yalnızca tanımlı token'ları (keyword, identifier, operatör, literal vb.) kabul eder. `@` MiniLang alfabetinde yoktur; lexer bu noktada token üretemez.

**Beklenen çıktı (Error Log):**

```text
Line 2: Lexical Error: Invalid character '@'
```

**Alternatif lexical hatalar:** kapanmamış `"string`, bozuk sayı `3.`, kapanmamış `/* yorum`.

---

### 2. Syntax Error (Sözdizimi Hatası)

**Örnek kod** — bildirim satırının sonunda `;` eksik:

```minilang
int x = 10
int y = 3;
```

**Neden hata?** Pass 2 (Parser) BNF kurallarına göre her bildirim `TYPE IDENTIFIER ... ';'` ile bitmelidir. Birinci satırda `;` olmadığı için parser bir sonraki `int` keyword'ünü beklenmedik yerde bulur ve gramer ihlali raporlar.

**Beklenen çıktı (Error Log):**

```text
Line 2: Syntax Error: Expected SEMICOLON, found KEYWORD (end of declaration)
```

**Alternatif syntax hatalar:** `if (x > 5 {` (eksik `)`), `print("hello"` (eksik `;` veya `)`).

---

### 3. Semantic Error (Anlamsal Hata)

Anlamsal kontroller aynı Pass 2 içinde yapılır; en az bir örnekle sunmanız yeterlidir.

#### 3a. Tanımlanmamış değişken (Undeclared)

```minilang
int x = 10;
x = y + 1;
```

**Neden hata?** `y` sembol tablosunda hiç tanımlanmamıştır. Parser ifadeyi okurken `y`'yi çözemez.

**Beklenen çıktı:**

```text
Line 2: Semantic Error: Undeclared variable 'y'
```

#### 3b. Tekrar tanım (Duplicate declaration)

```minilang
int x = 10;
int x = 5;
```

**Neden hata?** Aynı kapsamda `x` iki kez tanımlanamaz.

**Beklenen çıktı:**

```text
Line 2: Semantic Error: Duplicate declaration of variable 'x'
```

#### 3c. Tip uyuşmazlığı (Type mismatch)

```minilang
int x = 10;
x = 3.14;
```

**Neden hata?** `x` `int` tipinde tanımlı; sağ taraftaki `3.14` ise `float` literal. `int` değişkene doğrudan `float` atanamaz.

**Beklenen çıktı:**

```text
Line 2: Semantic Error: Type mismatch: cannot assign float value to int variable 'x'
```

---

### Demo akışı (sunum günü)

1. **PDF Örnek Program** → Analyze → yeşil başarı; Token Stream, Line Mapping, Symbol Table, AST, TAC sekmelerini göster.
2. Lexical örneği (`@`) → Error Log kırmızı, satır numarası görünsün.
3. Syntax örneği (eksik `;`) → aynı şekilde.
4. Semantic örneği (tanımsız değişken veya tip hatası) → aynı şekilde.
5. Navbar'daki **i** butonu → iki geçişli mimari ve sekme açıklamaları.

> Not: Lexer ve parser tamamen el yapımıdır; Lex, Yacc veya ANTLR kullanılmamıştır (proje dokümanı §5–§7).
