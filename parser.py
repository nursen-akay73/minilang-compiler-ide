"""
MiniLang Parser & Semantic Analyzer (Pass 2)
============================================
El yapımı Recursive Descent Parser.
Lexer'dan gelen token akışını tüketir; AST üretir ve anlam analizi yapar.
"""

from __future__ import annotations

import json

from lexer import Lexer, Token
from symbol_table import SymbolTable


# ------------------------------------------------------------------ #
#  AST yardımcıları (JSON uyumlu sözlük düğümleri)
# ------------------------------------------------------------------ #

def make_node(node_type: str, line: int, **fields) -> dict:
    """AST düğümü oluşturur; tüm düğümlerde satır numarası bulunur."""
    node = {"type": node_type, "line": line}
    node.update(fields)
    return node


# ------------------------------------------------------------------ #
#  Parser sınıfı
# ------------------------------------------------------------------ #

class Parser:
    """
    Recursive Descent Parser + Semantic Analyzer.

    Gramer özeti:
        program     -> statement*
        statement   -> declaration | assignment | if_stmt | while_stmt
                      | print_stmt | block
        declaration -> TYPE IDENTIFIER ('=' expression)? ';'
        assignment  -> IDENTIFIER '=' expression ';'
        if_stmt     -> 'if' '(' condition ')' block ('else' block)?
        while_stmt  -> 'while' '(' condition ')' block
        print_stmt  -> 'print' '(' expression ')' ';'
        block       -> '{' statement* '}'

        condition   -> logical_or
        logical_or  -> logical_and ('||' logical_and)*
        logical_and -> equality ('&&' equality)*
        equality    -> comparison (('==' | '!=') comparison)*
        comparison  -> expression (('<' | '>' | '<=' | '>=') expression)?

        expression  -> term (('+' | '-') term)*        # Düşük öncelik
        term        -> factor (('*' | '/') factor)*     # Yüksek öncelik
        factor      -> literal | identifier | '(' expression ')'
    """

    TYPE_KEYWORDS = {"int", "float"}

    def __init__(self, tokens: list[Token], symbol_table: SymbolTable | None = None):
        self.tokens = tokens
        self.pos = 0
        # Lexer'ın Pass 1 sembol tablosunu Pass 2'de tamamlar
        self.symbol_table = symbol_table or SymbolTable()
        self.errors: list[str] = []
        self.ast: dict | None = None

    # ------------------------------------------------------------------ #
    #  Token tüketimi
    # ------------------------------------------------------------------ #

    def _peek(self, offset: int = 0) -> Token | None:
        index = self.pos + offset
        if index >= len(self.tokens):
            return None
        return self.tokens[index]

    def _advance(self) -> Token | None:
        if self.pos >= len(self.tokens):
            return None
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _previous(self) -> Token | None:
        if self.pos == 0:
            return None
        return self.tokens[self.pos - 1]

    def _at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def _check(self, token_type: str, value: str | None = None) -> bool:
        token = self._peek()
        if token is None:
            return False
        if token.token_type != token_type:
            return False
        if value is not None and token.value != value:
            return False
        return True

    def _match(self, token_type: str, value: str | None = None) -> bool:
        if self._check(token_type, value):
            self._advance()
            return True
        return False

    def _expect(
        self,
        token_type: str,
        value: str | None = None,
        context: str = "",
    ) -> Token | None:
        token = self._peek()
        if token is not None and token.token_type == token_type:
            if value is None or token.value == value:
                return self._advance()

        line = token.line if token else "?"
        expected = value if value else token_type
        found = token.token_type if token else "EOF"
        message = f"Line {line}: Syntax Error: Expected {expected}, found {found}"
        if context:
            message += f" ({context})"
        self._report_error(message)
        return None

    # ------------------------------------------------------------------ #
    #  Hata yönetimi
    # ------------------------------------------------------------------ #

    def _report_error(self, message: str) -> None:
        """Semantic veya syntax hatasını kaydeder; program çökmez."""
        if message not in self.errors:
            self.errors.append(message)

    def _report_semantic(self, line: int, message: str) -> None:
        self._report_error(f"Line {line}: Semantic Error: {message}")

    def _synchronize(self) -> None:
        """
        Hata sonrası kurtarma: bir sonraki güvenli noktaya ( ; veya } ) atlar.
        Böylece tek hata tüm analizi durdurmaz.
        """
        while not self._at_end():
            token = self._peek()
            if token is None:
                return
            if token.token_type in {"SEMICOLON", "RBRACE"}:
                self._advance()
                return
            if token.token_type == "KEYWORD" and token.value in self.TYPE_KEYWORDS:
                return
            if token.token_type == "KEYWORD" and token.value in {
                "if", "else", "while", "print"
            }:
                return
            self._advance()

    # ------------------------------------------------------------------ #
    #  Semantic kontroller
    # ------------------------------------------------------------------ #

    def _resolve_identifier(self, name: str, line: int) -> str | None:
        """
        Tanımlayıcı kullanımında sembol tablosunu kontrol eder.
        Hata 1: Tanımlanmamış değişken kullanımı.
        """
        var_type = self.symbol_table.get_type(name)
        if var_type is None:
            self._report_semantic(
                line,
                f"Undeclared variable '{name}'",
            )
            return None
        return var_type

    def _check_type_assignment(
        self,
        target_name: str,
        target_type: str,
        source_type: str | None,
        line: int,
    ) -> None:
        """
        Hata 3: Tip uyuşmazlığı kontrolü.
        int değişkene float veya string atanamaz.
        """
        if source_type is None:
            return

        if target_type == "int" and source_type in {"float", "string"}:
            self._report_semantic(
                line,
                f"Type mismatch: cannot assign {source_type} value to int variable '{target_name}'",
            )
        elif target_type == "float" and source_type == "string":
            self._report_semantic(
                line,
                f"Type mismatch: cannot assign string value to float variable '{target_name}'",
            )

    def _literal_type(self, token: Token) -> str:
        if token.token_type == "INTEGER":
            return "int"
        if token.token_type == "FLOAT":
            return "float"
        if token.token_type == "STRING":
            return "string"
        return "unknown"

    def _combine_binary_types(
        self, left_type: str | None, right_type: str | None
    ) -> str | None:
        """İki operandın birleşik tipini çıkarır (ifade analizi için)."""
        if left_type is None or right_type is None:
            return None
        if left_type == "string" or right_type == "string":
            return "string"
        if left_type == "float" or right_type == "float":
            return "float"
        return "int"

    # ------------------------------------------------------------------ #
    #  Program ve ifadeler
    # ------------------------------------------------------------------ #

    def parse(self) -> dict | None:
        """
        Ana giriş noktası. AST'yi üretir ve JSON uyumlu sözlük döndürür.
        Hatalar olsa bile mümkün olduğunca AST oluşturulmaya çalışılır.
        """
        statements = self._parse_program()
        line = self.tokens[0].line if self.tokens else 1
        self.ast = make_node("Program", line=line, statements=statements)
        return self.ast

    def to_json(self, indent: int = 2) -> str:
        """AST'yi JSON string olarak döndürür."""
        if self.ast is None:
            self.parse()
        return json.dumps(self.ast, indent=indent, ensure_ascii=False)

    def _parse_program(self) -> list[dict]:
        statements: list[dict] = []
        while not self._at_end():
            stmt = self._parse_statement()
            if stmt is not None:
                statements.append(stmt)
        return statements

    def _parse_statement(self) -> dict | None:
        token = self._peek()
        if token is None:
            return None

        # Tip anahtar kelimesi ile başlıyorsa: değişken tanımı
        if token.token_type == "KEYWORD" and token.value in self.TYPE_KEYWORDS:
            return self._parse_declaration()

        if token.token_type == "IDENTIFIER":
            return self._parse_assignment()

        if token.token_type == "KEYWORD" and token.value == "if":
            return self._parse_if_statement()

        if token.token_type == "KEYWORD" and token.value == "while":
            return self._parse_while_statement()

        if token.token_type == "KEYWORD" and token.value == "print":
            return self._parse_print_statement()

        if token.token_type == "LBRACE":
            return self._parse_block()

        self._report_error(
            f"Line {token.line}: Syntax Error: Unexpected token {token.token_type}"
        )
        self._advance()
        self._synchronize()
        return None

    def _parse_declaration(self) -> dict | None:
        """
        Değişken tanımı: int x; veya float y = 3.14;
        Hata 2: Aynı değişkenin iki kez tanımlanması.
        """
        type_token = self._advance()
        if type_token is None:
            return None

        var_type = type_token.value
        name_token = self._expect("IDENTIFIER", context="variable name in declaration")
        if name_token is None:
            self._synchronize()
            return None

        line = type_token.line
        name = name_token.value

        # Hata 2: Yinelenen tanım
        try:
            self.symbol_table.declare(name, var_type)
        except ValueError:
            self._report_semantic(
                line,
                f"Duplicate declaration of variable '{name}'",
            )

        init_node = None

        if self._match("ASSIGN"):
            init_node, init_type = self._parse_expression()
            if self.symbol_table.is_declared(name):
                self._check_type_assignment(name, var_type, init_type, line)

        self._expect("SEMICOLON", context="end of declaration")

        symbol = self.symbol_table.lookup(name)
        return make_node(
            "VarDecl",
            line=line,
            var_type=var_type,
            name=name,
            memory_location=symbol.memory_location if symbol else None,
            scope=symbol.scope if symbol else "Global",
            initializer=init_node,
        )

    def _parse_assignment(self) -> dict | None:
        """
        Atama ifadesi: x = 5;
        Hata 1: Tanımlanmamış değişkene atama.
        Hata 3: Tip uyuşmazlığı.
        """
        name_token = self._advance()
        if name_token is None:
            return None

        line = name_token.line
        name = name_token.value

        target_type = self._resolve_identifier(name, line)

        if not self._expect("ASSIGN", context="assignment operator"):
            self._synchronize()
            return None

        value_node, source_type = self._parse_expression()

        if target_type is not None:
            self._check_type_assignment(name, target_type, source_type, line)

        self._expect("SEMICOLON", context="end of assignment")

        return make_node(
            "Assign",
            line=line,
            name=name,
            value=value_node,
        )

    def _parse_if_statement(self) -> dict:
        if_token = self._advance()
        line = if_token.line if if_token else 1

        self._expect("LPAREN", context="if condition")
        condition, _ = self._parse_condition()
        self._expect("RPAREN", context="if condition")

        then_branch = self._parse_block()
        else_branch = None

        if self._match("KEYWORD", "else"):
            else_branch = self._parse_block()

        return make_node(
            "IfStmt",
            line=line,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def _parse_while_statement(self) -> dict:
        while_token = self._advance()
        line = while_token.line if while_token else 1

        self._expect("LPAREN", context="while condition")
        condition, _ = self._parse_condition()
        self._expect("RPAREN", context="while condition")

        body = self._parse_block()

        return make_node(
            "WhileStmt",
            line=line,
            condition=condition,
            body=body,
        )

    def _parse_print_statement(self) -> dict:
        print_token = self._advance()
        line = print_token.line if print_token else 1

        self._expect("LPAREN", context="print argument")
        argument, _ = self._parse_expression()
        self._expect("RPAREN", context="print argument")
        self._expect("SEMICOLON", context="end of print statement")

        return make_node(
            "PrintStmt",
            line=line,
            argument=argument,
        )

    def _parse_block(self) -> dict:
        block_token = self._expect("LBRACE", context="start of block")
        line = block_token.line if block_token else 1

        statements: list[dict] = []
        while not self._at_end() and not self._check("RBRACE"):
            stmt = self._parse_statement()
            if stmt is not None:
                statements.append(stmt)

        self._expect("RBRACE", context="end of block")

        return make_node(
            "Block",
            line=line,
            statements=statements,
        )

    # ------------------------------------------------------------------ #
    #  Koşul ifadeleri (karşılaştırma ve mantıksal operatörler)
    # ------------------------------------------------------------------ #

    def _parse_condition(self) -> tuple[dict | None, str | None]:
        return self._parse_logical_or()

    def _parse_logical_or(self) -> tuple[dict | None, str | None]:
        left, left_type = self._parse_logical_and()

        while self._match("LOGICAL_OR"):
            op_token = self._previous()
            right, right_type = self._parse_logical_and()
            line = op_token.line if op_token else 1
            left = make_node(
                "BinaryOp",
                line=line,
                operator="||",
                left=left,
                right=right,
                result_type="bool",
            )
            left_type = "bool"

        return left, left_type

    def _parse_logical_and(self) -> tuple[dict | None, str | None]:
        left, left_type = self._parse_equality()

        while self._match("LOGICAL_AND"):
            op_token = self._previous()
            right, right_type = self._parse_equality()
            line = op_token.line if op_token else 1
            left = make_node(
                "BinaryOp",
                line=line,
                operator="&&",
                left=left,
                right=right,
                result_type="bool",
            )
            left_type = "bool"

        return left, left_type

    def _parse_equality(self) -> tuple[dict | None, str | None]:
        left, left_type = self._parse_comparison()

        while self._peek() is not None and self._peek().token_type in {"EQUAL", "NOT_EQUAL"}:
            op_token = self._advance()
            right, right_type = self._parse_comparison()
            line = op_token.line
            left = make_node(
                "BinaryOp",
                line=line,
                operator=op_token.value,
                left=left,
                right=right,
                result_type="bool",
            )
            left_type = "bool"

        return left, left_type

    def _parse_comparison(self) -> tuple[dict | None, str | None]:
        left, left_type = self._parse_expression()

        comparison_types = {
            "LESS_THAN", "GREATER_THAN", "LESS_EQUAL", "GREATER_EQUAL"
        }
        if self._peek() is not None and self._peek().token_type in comparison_types:
            op_token = self._advance()
            right, right_type = self._parse_expression()
            line = op_token.line
            left = make_node(
                "BinaryOp",
                line=line,
                operator=op_token.value,
                left=left,
                right=right,
                result_type="bool",
            )
            left_type = "bool"

        return left, left_type

    # ------------------------------------------------------------------ #
    #  Aritmetik ifadeler (işlem önceliği: * /  >  + -)
    # ------------------------------------------------------------------ #

    def _parse_expression(self) -> tuple[dict | None, str | None]:
        """Toplama ve çıkarma (düşük öncelik)."""
        return self._parse_term(additive=True)

    def _parse_term(self, additive: bool = False) -> tuple[dict | None, str | None]:
        """
        Çarpma ve bölme (yüksek öncelik).
        additive=True ise term (('+' | '-') term)* kuralını uygular.
        """
        left, left_type = self._parse_factor()

        # Yüksek öncelikli * ve /
        while self._peek() is not None and self._peek().token_type in {"MULTIPLY", "DIVIDE"}:
            op_token = self._advance()
            right, right_type = self._parse_factor()
            line = op_token.line
            result_type = self._combine_binary_types(left_type, right_type)
            left = make_node(
                "BinaryOp",
                line=line,
                operator=op_token.value,
                left=left,
                right=right,
                result_type=result_type,
            )
            left_type = result_type

        if not additive:
            return left, left_type

        # Düşük öncelikli + ve -
        while self._peek() is not None and self._peek().token_type in {"PLUS", "MINUS"}:
            op_token = self._advance()
            right, right_type = self._parse_term(additive=False)
            line = op_token.line
            result_type = self._combine_binary_types(left_type, right_type)
            left = make_node(
                "BinaryOp",
                line=line,
                operator=op_token.value,
                left=left,
                right=right,
                result_type=result_type,
            )
            left_type = result_type

        return left, left_type

    def _parse_factor(self) -> tuple[dict | None, str | None]:
        """Sayısal literal, tanımlayıcı veya parantez içi ifade."""
        token = self._peek()
        if token is None:
            return None, None

        # Parantezli ifade
        if token.token_type == "LPAREN":
            self._advance()
            node, expr_type = self._parse_expression()
            self._expect("RPAREN", context="closing parenthesis in expression")
            return node, expr_type

        # Sayısal veya string literal
        if token.token_type in {"INTEGER", "FLOAT", "STRING"}:
            literal = self._advance()
            return make_node(
                "Literal",
                line=literal.line,
                value=literal.value,
                literal_type=literal.token_type,
                result_type=self._literal_type(literal),
            ), self._literal_type(literal)

        # Tanımlayıcı
        if token.token_type == "IDENTIFIER":
            ident = self._advance()
            var_type = self._resolve_identifier(ident.value, ident.line)
            return make_node(
                "Identifier",
                line=ident.line,
                name=ident.value,
                result_type=var_type,
            ), var_type

        self._report_error(
            f"Line {token.line}: Syntax Error: Expected expression, found {token.token_type}"
        )
        self._advance()
        return None, None


# ------------------------------------------------------------------ #
#  Örnek kullanım ve test
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    # Başarılı örnek + semantic hata senaryoları
    sample_code = """
    int x = 10;
    float y = 3.14;
    int z = x + 2 * 3;
    if (x > 5 && y != 0.0) {
        print("Result is large");
    } else {
        x = x + 1;
    }
  int x;
    z = 3.14;
    w = 5;
    int bad = 3.14;
    """

    print("=== Lexer ===")
    lexer = Lexer(sample_code)
    tokens = lexer.tokenize()

    print("=== Parser & Semantic Analyzer ===")
    parser = Parser(tokens)
    ast = parser.parse()

    print("\n--- AST (JSON) ---")
    print(parser.to_json())

    print("\n--- Sembol Tablosu ---")
    for symbol in parser.symbol_table.all_symbols():
        print(symbol.to_dict())

    if parser.errors:
        print("\n--- Semantic / Syntax Hatalar ---")
        for error in parser.errors:
            print(error)
    else:
        print("\nHata bulunamadı.")
