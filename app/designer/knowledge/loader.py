"""Loader Design Knowledge Base.

Memuat seluruh aset YAML, memvalidasinya sekaligus, dan gagal cepat bila ada
yang tidak konsisten. Tidak ada bagian dari modul ini yang tahu tentang LLM
atau model gambar — DKB adalah pengetahuan desain murni.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from app.designer.knowledge.schemas import CATEGORIES
from app.designer.knowledge.schemas import EMPHASIS_LEVELS as EMPHASIS_ORDER
from app.designer.knowledge.validation import DesignKnowledgeBaseError, as_list, validate_all

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "design"


class DesignKnowledgeBase:
    """Akses baca-saja ke seluruh aset desain."""

    def __init__(
        self,
        registry: dict[str, Any],
        assets: dict[str, dict[str, dict[str, Any]]],
        root: Path,
    ):
        self._registry = registry
        self._assets = assets
        self.root = root

    # --- Pemuatan ---------------------------------------------------------

    @classmethod
    def load(
        cls,
        root: Path | None = None,
        strict_coherence: bool = True,
    ) -> "DesignKnowledgeBase":
        """Muat dan validasi seluruh knowledge base.

        Melempar DesignKnowledgeBaseError berisi SEMUA masalah sekaligus bila
        ada yang tidak konsisten.
        """
        root = Path(root or DEFAULT_ROOT)
        registry_path = root / "registry.yaml"
        if not registry_path.exists():
            raise DesignKnowledgeBaseError([f"{registry_path} tidak ditemukan"])

        registry = _read_yaml(registry_path)
        assets: dict[str, dict[str, dict[str, Any]]] = {}
        found_files: dict[str, list[str]] = {}
        problems: list[str] = []

        for category, schema in CATEGORIES.items():
            directory = root / schema.directory
            assets[category] = {}
            found_files[category] = []
            if not directory.is_dir():
                problems.append(f"folder '{schema.directory}/' tidak ditemukan")
                continue

            for path in sorted(directory.glob("*.yaml")):
                found_files[category].append(path.stem)
                try:
                    data = _read_yaml(path)
                except yaml.YAMLError as exc:
                    problems.append(f"{schema.directory}/{path.name}: YAML rusak — {exc}")
                    continue
                if not isinstance(data, dict):
                    problems.append(
                        f"{schema.directory}/{path.name}: isi harus berupa mapping"
                    )
                    continue
                assets[category][path.stem] = data

        problems.extend(validate_all(registry, assets, found_files, strict_coherence))

        if problems:
            raise DesignKnowledgeBaseError(problems)

        return cls(registry, assets, root)

    # --- Akses per kategori ----------------------------------------------

    def get_style(self, name: str) -> dict[str, Any]:
        return self._get("style", name)

    def get_layout(self, name: str) -> dict[str, Any]:
        return self._get("layout", name)

    def get_storytelling(self, name: str) -> dict[str, Any]:
        return self._get("storytelling", name)

    def get_typography(self, name: str) -> dict[str, Any]:
        return self._get("typography", name)

    def get_color_system(self, name: str) -> dict[str, Any]:
        return self._get("color_system", name)

    def get_icon_system(self, name: str) -> dict[str, Any]:
        return self._get("icon_system", name)

    def get_visualization(self, name: str) -> dict[str, Any]:
        return self._get("visualization_pattern", name)

    def get_audience_profile(self, name: str) -> dict[str, Any]:
        return self._get("audience_profile", name)

    def get_design_rules(self, name: str) -> dict[str, Any]:
        return self._get("design_rules", name)

    def list_styles(self) -> list[str]:
        return self._list("style")

    def list_layouts(self) -> list[str]:
        return self._list("layout")

    def list_storytelling(self) -> list[str]:
        return self._list("storytelling")

    def list_typography(self) -> list[str]:
        return self._list("typography")

    def list_color_systems(self) -> list[str]:
        return self._list("color_system")

    def list_icon_systems(self) -> list[str]:
        return self._list("icon_system")

    def list_visualizations(self) -> list[str]:
        return self._list("visualization_pattern")

    def list_audience_profiles(self) -> list[str]:
        return self._list("audience_profile")

    def list_design_rules(self) -> list[str]:
        return self._list("design_rules")

    # --- Kueri turunan ----------------------------------------------------

    @property
    def section_keys(self) -> list[str]:
        """Kosakata section yang diakui seluruh DKB."""
        return list(self._registry.get("section_keys") or [])

    @property
    def languages(self) -> list[str]:
        """Bahasa yang punya judul section lengkap."""
        return list(self._registry.get("languages") or [])

    @property
    def default_language(self) -> str:
        return self._registry.get("default_language") or (self.languages or ["en"])[0]

    def section_title(self, key: str, language: str | None = None) -> str:
        """Judul section sebagaimana tampil di kanvas.

        Satu-satunya sumber terjemahan judul. Design Agent tidak boleh
        menerjemahkan sendiri — terjemahan yang berbeda tiap run membuat laporan
        tidak dapat dibandingkan antar-periode.
        """
        language = language or self.default_language
        titles = (self._registry.get("section_titles") or {}).get(key)
        if not titles:
            raise KeyError(
                f"section '{key}' tidak punya judul di registry. "
                f"Tersedia: {', '.join(sorted(self._registry.get('section_titles') or {}))}"
            )
        if language not in titles:
            raise KeyError(
                f"section '{key}' tidak punya judul bahasa '{language}'. "
                f"Tersedia: {', '.join(sorted(titles))}"
            )
        return titles[language]

    def section_titles(self, keys: list[str], language: str | None = None) -> dict[str, str]:
        """Peta kunci section ke judulnya, untuk sekumpulan section sekaligus."""
        return {key: self.section_title(key, language) for key in keys}

    def style_for_audience(self, audience: str) -> str | None:
        """Style pertama yang mendukung audiens tersebut."""
        for style_id in self.list_styles():
            style = self.get_style(style_id)
            if audience in as_list(style.get("supported_audiences")):
                return style_id
        return None

    def resolve_style(self, name: str) -> dict[str, Any]:
        """Style beserta seluruh aset rujukannya yang sudah dimuat.

        Inilah bentuk yang berguna bagi Visual Design Agent: satu dokumen berisi
        semua keputusan desain yang saling terkait, tanpa perlu menelusuri
        referensi satu per satu.
        """
        style = self.get_style(name)
        visual = style.get("visual", {}) or {}
        return {
            "style": style,
            "layout": self.get_layout(visual["layout"]),
            "storytelling": self.get_storytelling(visual["storytelling"]),
            "typography": self.get_typography(visual["typography"]),
            "color_system": self.get_color_system(visual["color_system"]),
            "icon_system": self.get_icon_system(visual["icon_system"]),
            "design_rules": [self.get_design_rules(r) for r in visual.get("design_rules", [])],
            "visualization_patterns": [
                self.get_visualization(v) for v in visual.get("visualization_patterns", [])
            ],
            "audiences": [
                self.get_audience_profile(a) for a in as_list(style.get("supported_audiences"))
            ],
        }

    def effective_limits(self, style_name: str) -> dict[str, Any]:
        """Batas gabungan dari seluruh design_rules sebuah style.

        Bila dua aturan menetapkan batas berbeda, yang paling ketat menang —
        aturan tambahan hanya boleh memperketat, tidak pernah melonggarkan.
        """
        limits: dict[str, Any] = {}
        for rule_name in self.get_style(style_name).get("visual", {}).get("design_rules", []):
            for key, value in (self.get_design_rules(rule_name).get("limits") or {}).items():
                if not isinstance(value, (int, float)):
                    continue
                limits[key] = min(limits[key], value) if key in limits else value
        return limits

    def sections_for_style(self, style_name: str) -> dict[str, list[str]]:
        """Section yang selalu tampil dan kandidatnya."""
        style = self.get_style(style_name)
        return {
            "always": as_list(style.get("always_sections")),
            "candidates": as_list(style.get("candidate_sections")),
        }

    @property
    def data_keys(self) -> list[str]:
        """Jenis data yang mungkin tersedia dari Analysis Agent."""
        return list(self._registry.get("data_keys") or [])

    def section_requirement(self, key: str) -> dict[str, Any]:
        requirements = self._registry.get("section_requirements") or {}
        if key not in requirements:
            raise KeyError(
                f"section '{key}' tidak punya prasyarat. "
                f"Tersedia: {', '.join(sorted(requirements))}"
            )
        return requirements[key]

    def section_is_satisfied(self, key: str, available: Iterable[str]) -> bool:
        """Apakah prasyarat data sebuah section terpenuhi."""
        requirement = self.section_requirement(key)
        if requirement.get("always"):
            return True
        available = set(available)
        any_of = as_list(requirement.get("requires_any"))
        all_of = as_list(requirement.get("requires_all"))
        if any_of and not available & set(any_of):
            return False
        if all_of and not set(all_of) <= available:
            return False
        return bool(any_of or all_of)

    def applicable_sections(self, style_name: str, available: Iterable[str]) -> list[str]:
        """Section yang benar-benar akan dirender, dalam urutan reading flow.

        Inilah inti model ini: susunan kartu ditentukan data yang tersedia,
        bukan persona. Dua laporan dari persona yang sama menghasilkan halaman
        berbeda ketika datanya berbeda — dan section yang datanya tidak ada
        tidak pernah muncul sebagai kartu kosong.
        """
        available = set(available)
        unknown = available - set(self.data_keys)
        if unknown:
            raise KeyError(
                f"data key tak dikenal: {', '.join(sorted(unknown))}. "
                f"Tersedia: {', '.join(self.data_keys)}"
            )

        sections = self.sections_for_style(style_name)
        always = list(sections["always"])
        chosen = set(always)
        chosen |= {k for k in sections["candidates"] if self.section_is_satisfied(k, available)}

        style = self.get_style(style_name)
        story = self.get_storytelling(style["visual"]["storytelling"])
        flow = as_list(story.get("reading_flow"))
        ordered = [key for key in flow if key in chosen]

        return self._trim_to_capacity(ordered, always, story, style_name)

    def _trim_to_capacity(
        self,
        ordered: list[str],
        always: list[str],
        story: dict[str, Any],
        style_name: str,
    ) -> list[str]:
        """Pangkas ke kapasitas halaman bila data tersedia lebih dari yang muat.

        Yang dibuang lebih dulu adalah section beremphasis paling rendah, dan di
        antara yang setara, yang paling belakang dalam reading flow. Section
        always tidak pernah dibuang — termasuk catatan ketidakpastian.
        """
        capacity = self.page_capacity(style_name)
        if len(ordered) <= capacity:
            return ordered

        emphasis = story.get("emphasis_order") or {}
        rank = {level: i for i, level in enumerate(EMPHASIS_ORDER)}
        droppable = [k for k in ordered if k not in always]
        droppable.sort(
            key=lambda k: (-rank.get(emphasis.get(k, "secondary"), 1), -ordered.index(k))
        )

        dropped = set(droppable[: len(ordered) - capacity])
        return [key for key in ordered if key not in dropped]

    def page_capacity(self, style_name: str) -> int:
        """Jumlah section maksimum: yang paling ketat antara layout dan design rules."""
        resolved = self.resolve_style(style_name)
        caps = [resolved["layout"].get("max_sections")]
        caps += [r.get("limits", {}).get("max_sections") for r in resolved["design_rules"]]
        return min(c for c in caps if isinstance(c, int))

    def summary(self) -> dict[str, int]:
        """Jumlah aset per kategori — berguna untuk log startup."""
        return {category: len(pool) for category, pool in sorted(self._assets.items())}

    # --- Internal ---------------------------------------------------------

    def _get(self, category: str, name: str) -> dict[str, Any]:
        pool = self._assets.get(category, {})
        if name not in pool:
            available = ", ".join(sorted(pool)) or "(kosong)"
            raise KeyError(f"{category} '{name}' tidak ada. Tersedia: {available}")
        return pool[name]

    def _list(self, category: str) -> list[str]:
        return sorted(self._assets.get(category, {}))


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
