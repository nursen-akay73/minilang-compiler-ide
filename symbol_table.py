"""
MiniLang Sembol Tablosu (Symbol Table)
======================================
Pass 1 (Lexer): Tanımlayıcılar ilk görüldüklerinde kaydedilir (tip henüz bilinmez).
Pass 2 (Parser): Tip, bellek adresi ve semantik bilgiler tamamlanır.
"""


class Symbol:
    """
    Sembol tablosundaki tek bir değişken kaydını temsil eder.

    Zorunlu alanlar (proje şartnamesi):
        - name: Değişken adı
        - var_type: Veri tipi ('int' veya 'float')
        - memory_location: Simüle edilmiş bellek adresi (örn. 0x1000)
        - scope: Kapsam bilgisi (şimdilik 'Global')
    """

    def __init__(
        self,
        name: str,
        var_type: str,
        memory_location: str,
        scope: str = "Global",
    ):
        self.name = name
        self.var_type = var_type
        self.memory_location = memory_location
        self.scope = scope

    def to_dict(self) -> dict:
        """Sembol bilgisini sözlük (JSON uyumlu) formatında döndürür."""
        return {
            "name": self.name,
            "type": self.var_type,
            "memory_location": self.memory_location,
            "scope": self.scope,
        }

    def __repr__(self) -> str:
        return (
            f"Symbol(name={self.name!r}, type={self.var_type!r}, "
            f"addr={self.memory_location}, scope={self.scope!r})"
        )


class SymbolTable:
    """
    MiniLang değişkenlerini yöneten sembol tablosu.

    Bellek simülasyonu:
        - Başlangıç adresi: 0x1000
        - Her yeni değişken (int veya float) için adres +4 byte artar.
    """

    PENDING_TYPE = "?"  # Pass 1: tip henüz bilinmiyor
    PENDING_MEMORY = "—"

    BASE_ADDRESS = 0x1000
    ADDRESS_STEP = 4  # Her değişken için ayrılan simüle bellek birimi

    def __init__(self):
        # name -> Symbol eşlemesi (Global kapsam)
        self._symbols: dict[str, Symbol] = {}
        self._next_address: int = self.BASE_ADDRESS

    def _allocate_address(self) -> str:
        """Bir sonraki boş bellek adresini üretir ve sayacı ilerletir."""
        address = f"0x{self._next_address:X}"
        self._next_address += self.ADDRESS_STEP
        return address

    def register_from_lexer(self, name: str, scope: str = "Global") -> None:
        """
        Pass 1 (Lexer): Tanımlayıcı ilk kez görüldüğünde tabloya eklenir.
        Tip ve bellek adresi Pass 2'de tamamlanır.
        """
        if name not in self._symbols:
            self._symbols[name] = Symbol(
                name=name,
                var_type=self.PENDING_TYPE,
                memory_location=self.PENDING_MEMORY,
                scope=scope,
            )

    def declare(
        self,
        name: str,
        var_type: str,
        scope: str = "Global",
    ) -> Symbol:
        """
        Pass 2: Değişken tanımını tamamlar veya yeni kayıt oluşturur.

        Raises:
            ValueError: Aynı isimde değişken zaten tam tanımlıysa.
        """
        existing = self._symbols.get(name)
        if existing is not None:
            if existing.var_type != self.PENDING_TYPE:
                raise ValueError(f"Duplicate declaration: '{name}'")
            existing.var_type = var_type
            existing.memory_location = self._allocate_address()
            existing.scope = scope
            return existing

        symbol = Symbol(
            name=name,
            var_type=var_type,
            memory_location=self._allocate_address(),
            scope=scope,
        )
        self._symbols[name] = symbol
        return symbol

    def is_declared(self, name: str) -> bool:
        """Değişkenin tipi ile tam tanımlı olup olmadığını kontrol eder."""
        symbol = self.lookup(name)
        return symbol is not None and symbol.var_type != self.PENDING_TYPE

    def lookup(self, name: str) -> Symbol | None:
        """İsme göre sembol kaydını döndürür; yoksa None."""
        return self._symbols.get(name)

    def get_type(self, name: str) -> str | None:
        """Değişkenin veri tipini döndürür; tanımsız veya Pass 1 beklemesindeyse None."""
        symbol = self.lookup(name)
        if symbol is None or symbol.var_type == self.PENDING_TYPE:
            return None
        return symbol.var_type

    def all_symbols(self) -> list[Symbol]:
        """Tablodaki tüm sembolleri tanımlama sırasına göre döndürür."""
        return list(self._symbols.values())

    def to_dict(self) -> list[dict]:
        """Tüm sembol tablosunu JSON uyumlu liste olarak döndürür."""
        return [symbol.to_dict() for symbol in self.all_symbols()]
