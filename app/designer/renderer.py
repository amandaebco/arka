"""Template renderer — plain {{key}} substitution, no design logic."""

import re

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render(template: str, blocks: dict[str, str]) -> str:
    """Isi tiap {{key}} dengan blocks[key]. Placeholder tak dikenal jadi kosong."""
    text = PLACEHOLDER.sub(lambda m: blocks.get(m.group(1), "").strip(), template)
    # Rapikan sisa baris kosong dari blok yang tidak terpakai.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def placeholders(template: str) -> set:
    """Daftar placeholder di sebuah template — dipakai tes untuk deteksi drift."""
    return set(PLACEHOLDER.findall(template))
