"""Validasi Design Knowledge Base.

Validator mengumpulkan SEMUA masalah lebih dulu, baru melempar satu exception
berisi seluruh daftar. Gagal satu per satu akan memaksa perbaikan berulang kali
untuk knowledge base yang punya banyak salah ketik sekaligus.
"""

from typing import Any

from app.designer.knowledge.schemas import (
    CATEGORIES,
    COMMON_REQUIRED,
    EMPHASIS_LEVELS,
    ENUM_FIELDS,
    ENUM_LIST_FIELDS,
    SCHEMA_VERSION,
)


class DesignKnowledgeBaseError(Exception):
    """Knowledge base tidak konsisten; berisi seluruh masalah yang ditemukan."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        listed = "\n".join(f"  - {p}" for p in problems)
        super().__init__(
            f"Design Knowledge Base tidak valid ({len(problems)} masalah):\n{listed}"
        )


def dig(data: dict[str, Any], path: str) -> Any:
    """Ambil nilai bersarang lewat path bertitik; None bila tidak ada."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def as_list(value: Any) -> list[Any]:
    """Referensi boleh ditulis tunggal, sebagai daftar, atau sebagai kunci dict."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.keys())
    return value if isinstance(value, list) else [value]


def validate_registry(registry: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    version = registry.get("schema_version")
    if version != SCHEMA_VERSION:
        problems.append(
            f"registry.yaml: schema_version {version!r} tidak cocok dengan loader "
            f"(mengharapkan {SCHEMA_VERSION})"
        )

    section_keys = registry.get("section_keys") or []
    if not section_keys:
        problems.append("registry.yaml: 'section_keys' wajib ada dan tidak boleh kosong")

    problems.extend(_validate_languages(registry, section_keys))
    problems.extend(_validate_section_requirements(registry, section_keys))

    for schema in CATEGORIES.values():
        entries = registry.get(schema.registry_key)
        if entries is None:
            problems.append(f"registry.yaml: kunci '{schema.registry_key}' tidak ada")
            continue
        if not isinstance(entries, list):
            problems.append(f"registry.yaml: '{schema.registry_key}' harus berupa daftar")
            continue
        for name in sorted({e for e in entries if entries.count(e) > 1}):
            problems.append(f"registry.yaml: '{schema.registry_key}' memuat duplikat '{name}'")

    return problems


def _validate_section_requirements(
    registry: dict[str, Any], section_keys: list[str]
) -> list[str]:
    """Tiap section wajib menyatakan prasyarat datanya.

    Section tanpa prasyarat akan selalu terpilih dan berakhir sebagai kartu
    kosong — kegagalan yang justru ingin dicegah model ini.
    """
    problems: list[str] = []
    data_keys = set(registry.get("data_keys") or [])
    if not data_keys:
        problems.append("registry.yaml: 'data_keys' wajib ada dan tidak boleh kosong")

    requirements = registry.get("section_requirements") or {}
    for key in section_keys:
        entry = requirements.get(key)
        if not entry:
            problems.append(
                f"registry.yaml: section '{key}' tidak punya section_requirements"
            )
            continue
        if entry.get("always"):
            continue
        clauses = {k: entry.get(k) for k in ("requires_any", "requires_all")}
        if not any(clauses.values()):
            problems.append(
                f"registry.yaml: section '{key}' harus punya requires_any, "
                f"requires_all, atau always"
            )
            continue
        for clause, values in clauses.items():
            for value in as_list(values):
                if value not in data_keys:
                    problems.append(
                        f"registry.yaml: section '{key}' {clause} menyebut data key "
                        f"'{value}' yang tidak ada di data_keys"
                    )

    for key in sorted(set(requirements) - set(section_keys)):
        problems.append(
            f"registry.yaml: section_requirements memuat '{key}' yang tidak ada "
            f"di section_keys"
        )

    return problems


def _validate_languages(registry: dict[str, Any], section_keys: list[str]) -> list[str]:
    """Tiap section wajib punya judul di setiap bahasa yang didukung.

    Judul yang hilang berarti Design Agent akan menerjemahkan sendiri, dan
    terjemahan yang berbeda tiap run membuat laporan tak bisa dibandingkan.
    """
    problems: list[str] = []
    languages = registry.get("languages") or []
    if not languages:
        problems.append("registry.yaml: 'languages' wajib ada dan tidak boleh kosong")
        return problems

    default = registry.get("default_language")
    if default not in languages:
        problems.append(
            f"registry.yaml: default_language {default!r} tidak ada di languages {languages}"
        )

    titles = registry.get("section_titles") or {}
    for key in section_keys:
        entry = titles.get(key)
        if not entry:
            problems.append(f"registry.yaml: section '{key}' tidak punya section_titles")
            continue
        for language in languages:
            if not entry.get(language):
                problems.append(
                    f"registry.yaml: section '{key}' tidak punya judul bahasa '{language}'"
                )

    for key in sorted(set(titles) - set(section_keys)):
        problems.append(
            f"registry.yaml: section_titles memuat '{key}' yang tidak ada di section_keys"
        )

    return problems


def validate_asset(
    asset: dict[str, Any], category: str, filename: str, section_keys: list[str]
) -> list[str]:
    """Validasi satu aset terhadap schema kategorinya."""
    problems: list[str] = []
    schema = CATEGORIES[category]
    where = f"{schema.directory}/{filename}"

    for path in COMMON_REQUIRED + schema.required:
        if dig(asset, path) in (None, "", [], {}):
            problems.append(f"{where}: field wajib '{path}' hilang atau kosong")

    asset_id = asset.get("id")
    expected_id = filename.rsplit(".", 1)[0]
    if asset_id and asset_id != expected_id:
        problems.append(
            f"{where}: id '{asset_id}' tidak cocok dengan nama file '{expected_id}'"
        )

    declared = asset.get("category")
    if declared and declared != schema.category:
        problems.append(
            f"{where}: category '{declared}' salah, seharusnya '{schema.category}'"
        )

    for field_name, allowed in ENUM_FIELDS.get(category, {}).items():
        value = asset.get(field_name)
        if value is not None and value not in allowed:
            problems.append(
                f"{where}: '{field_name}' bernilai {value!r}, harus salah satu dari {allowed}"
            )

    for field_name, allowed in ENUM_LIST_FIELDS.get(category, {}).items():
        for value in as_list(asset.get(field_name)):
            if value not in allowed:
                problems.append(
                    f"{where}: '{field_name}' memuat {value!r}, harus salah satu dari {allowed}"
                )

    # Kunci section harus berasal dari kosakata di registry.
    for path in schema.section_key_fields:
        for key in as_list(dig(asset, path)):
            if key not in section_keys:
                problems.append(f"{where}: '{path}' memuat section key tak dikenal '{key}'")

    # Section yang selalu tampil tidak boleh sekaligus menjadi kandidat.
    always_sections = set(as_list(asset.get("always_sections")))
    candidate_sections = set(as_list(asset.get("candidate_sections")))
    for key in sorted(always_sections & candidate_sections):
        problems.append(
            f"{where}: section '{key}' terdaftar sebagai always sekaligus kandidat"
        )

    problems.extend(_validate_emphasis(asset, where))
    return problems


def _validate_emphasis(asset: dict[str, Any], where: str) -> list[str]:
    """Emphasis order: level dibatasi, dan 'dominant' hanya boleh satu."""
    problems: list[str] = []
    emphasis = asset.get("emphasis_order")
    if not isinstance(emphasis, dict):
        return problems

    for key, level in emphasis.items():
        if level not in EMPHASIS_LEVELS:
            problems.append(
                f"{where}: emphasis_order['{key}'] = {level!r}, "
                f"harus salah satu dari {EMPHASIS_LEVELS}"
            )
    dominant = [k for k, v in emphasis.items() if v == "dominant"]
    if len(dominant) > 1:
        problems.append(
            f"{where}: emphasis_order punya {len(dominant)} elemen 'dominant' "
            f"({', '.join(sorted(dominant))}); hanya boleh satu"
        )
    return problems


def validate_references(assets: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """Pastikan setiap referensi antar-aset menunjuk ke aset yang benar-benar ada."""
    problems: list[str] = []

    for category, schema in CATEGORIES.items():
        for asset_id, asset in assets.get(category, {}).items():
            where = f"{schema.directory}/{asset_id}.yaml"
            for path, target_category in schema.references:
                pool = assets.get(target_category, {})
                for ref in as_list(dig(asset, path)):
                    if ref not in pool:
                        available = ", ".join(sorted(pool)) or "(kosong)"
                        problems.append(
                            f"{where}: '{path}' menunjuk {target_category} '{ref}' "
                            f"yang tidak ada. Tersedia: {available}"
                        )

    return problems


def validate_coherence(assets: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """Pemeriksaan lintas-aset: kombinasi yang valid tapi tidak masuk akal."""
    problems: list[str] = []
    styles = assets.get("style", {})
    stories = assets.get("storytelling", {})
    layouts = assets.get("layout", {})
    audiences = assets.get("audience_profile", {})

    for style_id, style in styles.items():
        where = f"styles/{style_id}.yaml"
        visual = style.get("visual", {}) or {}
        layout_id = visual.get("layout")
        story_id = visual.get("storytelling")
        story = stories.get(story_id)
        layout = layouts.get(layout_id)

        # Layout pilihan style harus direkomendasikan oleh pola naratifnya.
        if story and layout_id:
            recommended = story.get("recommended_layouts") or []
            if layout_id not in recommended:
                problems.append(
                    f"{where}: layout '{layout_id}' tidak ada di recommended_layouts "
                    f"storytelling '{story_id}' ({', '.join(recommended)})"
                )

        always_sections = as_list(style.get("always_sections"))
        candidate_sections = as_list(style.get("candidate_sections"))

        # Section yang selalu tampil harus muat di layout, apa pun datanya.
        if layout:
            max_sections = layout.get("max_sections")
            if isinstance(max_sections, int) and len(always_sections) > max_sections:
                problems.append(
                    f"{where}: {len(always_sections)} section always melebihi "
                    f"max_sections layout '{layout_id}' ({max_sections})"
                )

        # Seluruh section style harus punya tempat di reading flow, karena flow
        # itulah yang menentukan urutan saat kandidat terpilih.
        if story:
            flow = set(as_list(story.get("reading_flow")))
            for key in always_sections + candidate_sections:
                if key not in flow:
                    problems.append(
                        f"{where}: section '{key}' tidak ada di reading_flow "
                        f"storytelling '{story_id}'"
                    )

        # Densitas style harus cocok dengan preferensi audiensnya.
        densities = set(style.get("densities") or [])
        for audience_id in as_list(style.get("supported_audiences")):
            audience = audiences.get(audience_id)
            if not audience:
                continue
            preferred = audience.get("preferred_density")
            if preferred not in densities:
                problems.append(
                    f"{where}: audiens '{audience_id}' memilih densitas '{preferred}', "
                    f"tidak ada di densities style ({', '.join(sorted(densities))})"
                )
            # Pola naratif audiens dan style sebaiknya sejalan.
            if story_id and audience.get("preferred_storytelling") != story_id:
                problems.append(
                    f"{where}: storytelling '{story_id}' berbeda dari preferensi audiens "
                    f"'{audience_id}' ('{audience.get('preferred_storytelling')}')"
                )

    # Tiap audiens harus punya minimal satu style yang melayaninya.
    served = {a for s in styles.values() for a in as_list(s.get("supported_audiences"))}
    for audience_id in sorted(set(audiences) - served):
        problems.append(
            f"audience_profiles/{audience_id}.yaml: tidak ada style yang mendukung "
            f"audiens ini"
        )

    return problems


def validate_all(
    registry: dict[str, Any],
    assets: dict[str, dict[str, dict[str, Any]]],
    found_files: dict[str, list[str]],
    strict_coherence: bool = True,
) -> list[str]:
    """Jalankan seluruh lapisan validasi dan kembalikan gabungan masalahnya."""
    problems = validate_registry(registry)
    section_keys = registry.get("section_keys") or []

    for category, schema in CATEGORIES.items():
        listed = set(registry.get(schema.registry_key) or [])
        on_disk = set(found_files.get(category, []))

        for missing in sorted(listed - on_disk):
            problems.append(
                f"registry.yaml mendaftarkan {schema.registry_key} '{missing}' "
                f"tetapi {schema.directory}/{missing}.yaml tidak ada"
            )
        for unlisted in sorted(on_disk - listed):
            problems.append(
                f"{schema.directory}/{unlisted}.yaml ada di disk tetapi tidak terdaftar "
                f"di registry.yaml pada '{schema.registry_key}'"
            )

        for asset_id, asset in assets.get(category, {}).items():
            problems.extend(validate_asset(asset, category, f"{asset_id}.yaml", section_keys))

    problems.extend(validate_references(assets))
    if strict_coherence:
        problems.extend(validate_coherence(assets))

    return problems
