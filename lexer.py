"""
MiniLang Lexer (Pass 1 - Sözcük Analizci)
=========================================
El yapımı (hand-coded) lexer. Hazır derleyici üreteçleri kullanılmamıştır.
Kaynak kodu karakter karakter okuyarak token listesi üretir.
Pass 1 sembol tablosuna tanımlayıcıları kaydeder; yorum satırlarını atlar.
"""

from symbol_table import SymbolTable


# MiniLang anahtar kelimeleri
KEYWORDS = {"int", "float", "if", "else", "while", "print"}

# Tek karakterli operatör ve ayraçlar
SINGLE_CHAR_TOKENS = {
    "+": "PLUS",
    "-": "MINUS",
    "*": "MULTIPLY",
    "/": "DIVIDE",
    "<": "LESS_THAN",
    ">": "GREATER_THAN",
    "=": "ASSIGN",
    ";": "SEMICOLON",
    ",": "COMMA",
    "(": "LPAREN",
    ")": "RPAREN",
    "{": "LBRACE",
    "}": "RBRACE",
}

# İki karakterli operatörler (ilk karakter -> olası ikinci karakterler)
DOUBLE_CHAR_OPERATORS = {
    "=": {"=": "EQUAL"},
    "!": {"=": "NOT_EQUAL"},
    "<": {"=": "LESS_EQUAL"},
    ">": {"=": "GREATER_EQUAL"},
    "&": {"&": "LOGICAL_AND"},
    "|": {"|": "LOGICAL_OR"},
}


class Token:
    """Bir token'ı temsil eder: satır numarası, tip ve değer."""

    def __init__(self, line: int, token_type: str, value: str):
        self.line = line
        self.token_type = token_type
        self.value = value

    def __repr__(self) -> str:
        return f"({self.line}, {self.token_type}, {self.value!r})"

    def as_tuple(self) -> tuple:
        """(Satır, Tip, Değer) formatında döndürür."""
        return (self.line, self.token_type, self.value)


class Lexer:
    """
    MiniLang kaynak kodunu karakter karakter okuyarak tokenize eder.
    State-machine mantığı: her adımda mevcut karaktere göre uygun okuma
    fonksiyonuna yönlendirilir.
    """

    def __init__(self, source: str, symbol_table: SymbolTable | None = None):
        self.source = source
        self.pos = 0          # Mevcut okuma konumu
        self.line = 1         # Mevcut satır numarası
        self.tokens: list[Token] = []
        self.errors: list[str] = []
        # Pass 1 sembol tablosu (PDF şartnamesi)
        self.symbol_table = symbol_table or SymbolTable()

    # ------------------------------------------------------------------ #
    #  Yardımcı okuma fonksiyonları
    # ------------------------------------------------------------------ #

    def _peek(self, offset: int = 0) -> str | None:
        """offset kadar ilerideki karakteri döndürür; sınır dışıysa None."""
        index = self.pos + offset
        if index >= len(self.source):
            return None
        return self.source[index]

    def _advance(self) -> str | None:
        """Bir karakter ilerler; okunan karakteri döndürür."""
        if self.pos >= len(self.source):
            return None
        char = self.source[self.pos]
        self.pos += 1
        if char == "\n":
            self.line += 1
        return char

    def _is_at_end(self) -> bool:
        return self.pos >= len(self.source)

    # ------------------------------------------------------------------ #
    #  Boşluk atlama
    # ------------------------------------------------------------------ #

    def _skip_whitespace(self) -> None:
        """Boşluk, tab ve satır sonu karakterlerini atlar."""
        while not self._is_at_end():
            char = self._peek()
            if char in " \t\r\n":
                self._advance()
            else:
                break

    def _skip_comment(self) -> bool:
        """
        Yorum satırlarını atlar.
        Desteklenen: // tek satır, /* çok satır */
        """
        if self._peek() == "/" and self._peek(1) == "/":
            while self._peek() is not None and self._peek() != "\n":
                self._advance()
            return True

        if self._peek() == "/" and self._peek(1) == "*":
            start_line = self.line
            self._advance()
            self._advance()
            while not self._is_at_end():
                if self._peek() == "*" and self._peek(1) == "/":
                    self._advance()
                    self._advance()
                    return True
                self._advance()
            self.errors.append(
                f"Line {start_line}: Lexical Error: Unterminated block comment"
            )
            return True

        return False

    # ------------------------------------------------------------------ #
    #  Token okuma fonksiyonları
    # ------------------------------------------------------------------ #

    def _read_number(self, start_line: int) -> None:
        """
        Tam sayı (INTEGER) veya ondalıklı sayı (FLOAT) okur.
        Örnek: 42 -> INTEGER, 3.14 -> FLOAT
        """
        lexeme = ""

        # Tam sayı kısmı
        while self._peek() is not None and self._peek().isdigit():
            lexeme += self._advance()

        # Ondalık kısım var mı?
        if (
            self._peek() == "."
            and self._peek(1) is not None
            and self._peek(1).isdigit()
        ):
            lexeme += self._advance()  # '.'
            while self._peek() is not None and self._peek().isdigit():
                lexeme += self._advance()
            # Hatalı sayı: 3.14.5 gibi
            if self._peek() == ".":
                self.errors.append(
                    f"Line {start_line}: Lexical Error: Malformed number '{lexeme}.'"
                )
            self.tokens.append(Token(start_line, "FLOAT", lexeme))
        else:
            self.tokens.append(Token(start_line, "INTEGER", lexeme))

    def _read_identifier_or_keyword(self, start_line: int) -> None:
        """
        Tanımlayıcı (IDENTIFIER) veya anahtar kelime (KEYWORD) okur.
        Harf ile başlar; harf ve rakam içerebilir.
        """
        lexeme = ""

        while self._peek() is not None and (self._peek().isalnum() or self._peek() == "_"):
            lexeme += self._advance()

        if lexeme in KEYWORDS:
            self.tokens.append(Token(start_line, "KEYWORD", lexeme))
        else:
            self.tokens.append(Token(start_line, "IDENTIFIER", lexeme))
            # Pass 1: tanımlayıcıyı sembol tablosuna kaydet
            self.symbol_table.register_from_lexer(lexeme)

    def _read_string(self, start_line: int) -> None:
        """Çift tırnak içindeki STRING literal okur."""
        # Açılış tırnağını tüket
        self._advance()

        lexeme = ""
        while not self._is_at_end():
            char = self._peek()

            if char == '"':
                self._advance()  # Kapanış tırnağı
                self.tokens.append(Token(start_line, "STRING", lexeme))
                return

            if char == "\n":
                self.errors.append(
                    f"Line {start_line}: Lexical Error: Unterminated string literal"
                )
                return

            lexeme += self._advance()

        # Dosya sonuna ulaşıldı, tırnak kapanmadı
        self.errors.append(
            f"Line {start_line}: Lexical Error: Unterminated string literal"
        )

    def _read_operator_or_delimiter(self, start_line: int, first_char: str) -> None:
        """
        Operatör veya ayraç okur.
        Önce iki karakterli eşleşmeler denenir (==, !=, <=, >=, &&, ||),
        ardından tek karakterli token'lara bakılır.
        """
        # İki karakterli operatör kontrolü
        if first_char in DOUBLE_CHAR_OPERATORS:
            second = self._peek(1)
            if second in DOUBLE_CHAR_OPERATORS[first_char]:
                token_type = DOUBLE_CHAR_OPERATORS[first_char][second]
                self._advance()  # İlk karakter
                self._advance()  # İkinci karakter
                self.tokens.append(Token(start_line, token_type, first_char + second))
                return

        # Tek karakterli operatör veya ayraç
        if first_char in SINGLE_CHAR_TOKENS:
            self._advance()
            self.tokens.append(
                Token(start_line, SINGLE_CHAR_TOKENS[first_char], first_char)
            )
            return

        # Tanınmayan operatör karakteri (ör. tek başına '!' veya '&')
        self.errors.append(
            f"Line {start_line}: Lexical Error: Invalid character {first_char!r}"
        )
        self._advance()

    def _report_invalid_character(self, char: str) -> None:
        """Geçersiz karakter için hata kaydeder ve karakteri atlar."""
        self.errors.append(
            f"Line {self.line}: Lexical Error: Invalid character {char!r}"
        )
        self._advance()

    # ------------------------------------------------------------------ #
    #  Ana tokenize döngüsü (State Machine)
    # ------------------------------------------------------------------ #

    def tokenize(self) -> list[Token]:
        """
        Kaynak kodu baştan sona tarar ve token listesi döndürür.
        Hatalar self.errors listesinde toplanır; program çökmez.
        """
        while not self._is_at_end():
            self._skip_whitespace()
            if self._skip_comment():
                continue
            if self._is_at_end():
                break

            start_line = self.line
            char = self._peek()

            # Durum 1: Sayısal literal
            if char is not None and char.isdigit():
                self._read_number(start_line)

            # Durum 2: Tanımlayıcı veya anahtar kelime (harf ile başlar)
            elif char is not None and char.isalpha():
                self._read_identifier_or_keyword(start_line)

            # Durum 3: String literal
            elif char == '"':
                self._read_string(start_line)

            # Durum 4: Operatör veya ayraç
            elif char in SINGLE_CHAR_TOKENS or char in DOUBLE_CHAR_OPERATORS:
                self._read_operator_or_delimiter(start_line, char)

            # Durum 5: '!' tek başına geçersiz; '!=' için kontrol
            elif char == "!":
                self._read_operator_or_delimiter(start_line, char)

            # Durum 6: '&' ve '|' için kontrol (&&, ||)
            elif char in ("&", "|"):
                self._read_operator_or_delimiter(start_line, char)

            # Durum 7: Geçersiz karakter
            else:
                self._report_invalid_character(char)

        return self.tokens

    def get_token_tuples(self) -> list[tuple]:
        """Token listesini (satır, tip, değer) tuple listesi olarak döndürür."""
        return [token.as_tuple() for token in self.tokens]


# ------------------------------------------------------------------ #
#  Örnek kullanım ve test
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    sample_code = """
    int x = 10;
    float y = 3.14;
    if (x > 5 && y != 0.0) {
        print("Result is large");
    } else {
        x = x + 1;
    }
    while (x < 20) {
        x = x + 1;
    }
    int bad = @invalid;
    """

    lexer = Lexer(sample_code)
    tokens = lexer.tokenize()

    print("=== Token Listesi ===")
    for token in tokens:
        print(token.as_tuple())

    if lexer.errors:
        print("\n=== Lexical Hatalar ===")
        for error in lexer.errors:
            print(error)
    else:
        print("\nLexical hata bulunamadı.")
