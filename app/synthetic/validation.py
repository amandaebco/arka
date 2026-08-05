from typing import Any


class DatasetValidationError(ValueError):
    """Raised when synthetic data violates a canonical consistency rule."""


def _ids(dataset: dict[str, list[dict[str, Any]]], table: str) -> set[str]:
    return {str(row["id"]) for row in dataset[table]}


def _require_unique(
    dataset: dict[str, list[dict[str, Any]]], table: str, columns: tuple[str, ...]
) -> None:
    seen: set[tuple[str, ...]] = set()
    for row in dataset[table]:
        key = tuple(str(row[column]) for column in columns)
        if key in seen:
            joined = ", ".join(columns)
            raise DatasetValidationError(f"Duplicate {table} value for ({joined}): {key}")
        seen.add(key)


def _require_foreign_key(
    dataset: dict[str, list[dict[str, Any]]],
    child_table: str,
    child_column: str,
    parent_table: str,
    *,
    nullable: bool = False,
) -> None:
    parent_ids = _ids(dataset, parent_table)
    for row in dataset[child_table]:
        value = str(row[child_column])
        if nullable and not value:
            continue
        if value not in parent_ids:
            raise DatasetValidationError(
                f"Orphan {child_table}.{child_column}={value}; parent {parent_table} not found"
            )


def _require_exactly_one_target(dataset: dict[str, list[dict[str, Any]]], table: str) -> None:
    for row in dataset[table]:
        target_count = int(bool(row["equipment_id"])) + int(bool(row["component_id"]))
        if target_count != 1:
            raise DatasetValidationError(f"{table} row must target exactly one asset: {row}")


def validate_dataset(dataset: dict[str, list[dict[str, Any]]]) -> None:
    """Validate uniqueness and referential integrity before loading."""
    unique_rules = {
        "plants": [("id",), ("canonical_id",), ("code",)],
        "production_lines": [("id",), ("canonical_id",), ("plant_id", "code")],
        "equipment": [("id",), ("canonical_id",), ("tag_number",)],
        "components": [("id",), ("canonical_id",), ("equipment_id", "tag_number")],
        "asset_identifiers": [
            ("id",),
            ("source_system", "identifier_type", "identifier_value"),
        ],
        "sensors": [("id",), ("canonical_id",), ("tag_name",)],
        "observations": [("id",), ("sensor_id", "observed_at")],
        "alarms": [("id",), ("canonical_id",)],
        "operating_states": [("id",), ("canonical_id",), ("code",)],
        "equipment_operating_states": [("id",), ("equipment_id", "started_at")],
        "symptoms": [("id",), ("canonical_id",), ("code",)],
        "failure_modes": [("id",), ("canonical_id",), ("code",)],
        "causes": [("id",), ("canonical_id",), ("code",)],
        "failure_events": [("id",), ("canonical_id",), ("event_number",)],
        "failure_event_causes": [("id",), ("failure_event_id", "cause_id")],
        "damages": [("id",)],
        "technicians": [("id",), ("canonical_id",), ("employee_number",)],
        "spare_parts": [("id",), ("canonical_id",), ("part_number",)],
        "work_orders": [("id",), ("canonical_id",), ("work_order_number",)],
        "maintenance_activities": [("id",), ("work_order_id", "sequence_number")],
        "activity_targets": [("id",)],
    }
    for table, column_sets in unique_rules.items():
        for columns in column_sets:
            _require_unique(dataset, table, columns)

    foreign_keys = [
        ("production_lines", "plant_id", "plants", False),
        ("equipment", "production_line_id", "production_lines", False),
        ("components", "equipment_id", "equipment", False),
        ("asset_identifiers", "equipment_id", "equipment", True),
        ("asset_identifiers", "component_id", "components", True),
        ("sensors", "equipment_id", "equipment", True),
        ("sensors", "component_id", "components", True),
        ("observations", "sensor_id", "sensors", False),
        ("alarms", "sensor_id", "sensors", False),
        ("equipment_operating_states", "equipment_id", "equipment", False),
        ("equipment_operating_states", "operating_state_id", "operating_states", False),
        ("failure_events", "equipment_id", "equipment", False),
        ("failure_events", "component_id", "components", True),
        ("failure_event_symptoms", "failure_event_id", "failure_events", False),
        ("failure_event_symptoms", "symptom_id", "symptoms", False),
        ("failure_event_failure_modes", "failure_event_id", "failure_events", False),
        ("failure_event_failure_modes", "failure_mode_id", "failure_modes", False),
        ("failure_event_causes", "failure_event_id", "failure_events", False),
        ("failure_event_causes", "cause_id", "causes", False),
        ("damages", "failure_event_id", "failure_events", False),
        ("damages", "component_id", "components", True),
        ("alarm_symptoms", "alarm_id", "alarms", False),
        ("alarm_symptoms", "symptom_id", "symptoms", False),
        ("alarm_failure_events", "alarm_id", "alarms", False),
        ("alarm_failure_events", "failure_event_id", "failure_events", False),
        ("work_orders", "equipment_id", "equipment", False),
        ("maintenance_activities", "work_order_id", "work_orders", False),
        ("activity_technicians", "activity_id", "maintenance_activities", False),
        ("activity_technicians", "technician_id", "technicians", False),
        ("activity_spare_parts", "activity_id", "maintenance_activities", False),
        ("activity_spare_parts", "spare_part_id", "spare_parts", False),
        ("activity_targets", "activity_id", "maintenance_activities", False),
        ("activity_targets", "equipment_id", "equipment", True),
        ("activity_targets", "component_id", "components", True),
        ("work_order_failure_events", "work_order_id", "work_orders", False),
        ("work_order_failure_events", "failure_event_id", "failure_events", False),
    ]
    for child_table, child_column, parent_table, nullable in foreign_keys:
        _require_foreign_key(dataset, child_table, child_column, parent_table, nullable=nullable)

    for table in ("asset_identifiers", "sensors", "activity_targets"):
        _require_exactly_one_target(dataset, table)
