"""Definisi schema untuk aset Design Knowledge Base.

Schema dideklarasikan sebagai data, bukan kode, supaya menambah kategori aset
baru hanya berarti menambah satu entri di sini — bukan mengubah loader atau
validator.
"""

from dataclasses import dataclass, field

SCHEMA_VERSION = 4

# Field yang wajib ada di semua aset, apa pun kategorinya.
COMMON_REQUIRED = ["id", "name", "category", "description"]


@dataclass(frozen=True)
class CategorySchema:
    """Aturan satu kategori aset.

    directory   : nama folder di bawah design/
    registry_key: kunci daftar di registry.yaml
    category    : nilai yang harus ditulis di field 'category' tiap file
    required    : field wajib di tingkat akar, boleh memakai path bertitik
    references  : (path field, kategori tujuan) — divalidasi sebagai referensi
    section_key_fields : field yang isinya harus berupa kunci section kanonik
    """

    directory: str
    registry_key: str
    category: str
    required: list[str] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)
    section_key_fields: list[str] = field(default_factory=list)


CATEGORIES: dict[str, CategorySchema] = {
    "style": CategorySchema(
        directory="styles",
        registry_key="styles",
        category="style",
        required=[
            "metadata",
            "supported_audiences",
            "communication_goals",
            "report_types",
            "densities",
            "decision_types",
            "always_sections",
            "candidate_sections",
            "presentation",
            "presentation.reference",
            "presentation.mood",
            "presentation.finish",
            "visual",
            "visual.layout",
            "visual.storytelling",
            "visual.typography",
            "visual.color_system",
            "visual.icon_system",
            "visual.design_rules",
            "visual.visualization_patterns",
        ],
        references=[
            ("supported_audiences", "audience_profile"),
            ("visual.layout", "layout"),
            ("visual.storytelling", "storytelling"),
            ("visual.typography", "typography"),
            ("visual.color_system", "color_system"),
            ("visual.icon_system", "icon_system"),
            ("visual.design_rules", "design_rules"),
            ("visual.visualization_patterns", "visualization_pattern"),
        ],
        section_key_fields=["always_sections", "candidate_sections"],
    ),
    "layout": CategorySchema(
        directory="layouts",
        registry_key="layouts",
        category="layout",
        required=[
            "metadata",
            "orientation",
            "columns",
            "bands",
            "section_order",
            "card_chrome",
            "card_chrome.header",
            "card_chrome.chips",
            "spacing",
            "alignment",
            "responsive_behavior",
        ],
        section_key_fields=["section_order"],
    ),
    "storytelling": CategorySchema(
        directory="storytelling",
        registry_key="storytelling",
        category="storytelling",
        required=[
            "metadata",
            "communication_sequence",
            "reading_flow",
            "emphasis_order",
            "recommended_layouts",
        ],
        references=[("recommended_layouts", "layout")],
        section_key_fields=["reading_flow", "emphasis_order", "closing_element"],
    ),
    "typography": CategorySchema(
        directory="typography",
        registry_key="typography",
        category="typography",
        required=["metadata", "family", "scale", "hierarchy", "spacing", "emphasis"],
    ),
    "color_system": CategorySchema(
        directory="color_system",
        registry_key="color_system",
        category="color_system",
        required=["metadata", "primary", "secondary", "severity", "background", "accessibility"],
    ),
    "icon_system": CategorySchema(
        directory="icon_system",
        registry_key="icon_system",
        category="icon_system",
        required=["metadata", "style", "line_weight", "icon_grid", "usage_policy",
                  "spacing", "sizing"],
    ),
    "visualization_pattern": CategorySchema(
        directory="visualization_patterns",
        registry_key="visualization_patterns",
        category="visualization_pattern",
        required=[
            "metadata",
            "when_to_use",
            "when_to_avoid",
            "preferred_placement",
            "visual_emphasis",
        ],
    ),
    "audience_profile": CategorySchema(
        directory="audience_profiles",
        registry_key="audience_profiles",
        category="audience_profile",
        required=[
            "metadata",
            "reading_time_seconds",
            "preferred_density",
            "preferred_storytelling",
            "preferred_layout",
            "terminology",
            "visual_emphasis",
        ],
        references=[
            ("preferred_storytelling", "storytelling"),
            ("preferred_layout", "layout"),
        ],
        section_key_fields=["visual_emphasis"],
    ),
    "design_rules": CategorySchema(
        directory="design_rules",
        registry_key="design_rules",
        category="design_rules",
        required=["metadata", "whitespace", "font_hierarchy", "limits", "readability",
                  "accessibility"],
    ),
}

# Nilai enum yang dibatasi.
EMPHASIS_LEVELS = ["dominant", "primary", "secondary", "tertiary"]
DENSITIES = ["low", "medium", "high"]
ORIENTATIONS = ["portrait", "landscape", "square"]
ACTION_DIMENSIONS = ["horizon", "owner", "tradeoff"]

ENUM_FIELDS = {
    "layout": {"orientation": ORIENTATIONS},
    "audience_profile": {"preferred_density": DENSITIES},
    "visualization_pattern": {"visual_emphasis": EMPHASIS_LEVELS},
}

# Field bernilai daftar yang isinya dibatasi enum.
ENUM_LIST_FIELDS = {
    "style": {"densities": DENSITIES},
    "audience_profile": {"action_dimensions": ACTION_DIMENSIONS},
    "storytelling": {"action_dimensions": ACTION_DIMENSIONS},
}
