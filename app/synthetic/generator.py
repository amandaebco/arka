import argparse
import csv
import json
import random
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_SEED = 20260721
NAMESPACE = uuid.UUID("f62b9b7c-40f2-4e67-a3d7-f693484389e5")

FIELD_ORDER = {
    "plants": ["id", "canonical_id", "code", "name", "description"],
    "production_lines": [
        "id",
        "plant_id",
        "canonical_id",
        "code",
        "name",
        "description",
    ],
    "equipment": [
        "id",
        "production_line_id",
        "canonical_id",
        "tag_number",
        "name",
        "equipment_type",
        "manufacturer",
        "model",
        "serial_number",
        "commissioned_at",
        "status",
    ],
    "components": [
        "id",
        "equipment_id",
        "canonical_id",
        "tag_number",
        "name",
        "component_type",
        "manufacturer",
        "model",
        "serial_number",
        "status",
    ],
    "asset_identifiers": [
        "id",
        "equipment_id",
        "component_id",
        "source_system",
        "identifier_type",
        "identifier_value",
        "is_primary",
        "source_updated_at",
        "ingested_at",
    ],
    "operating_states": ["id", "canonical_id", "code", "name", "description"],
    "equipment_operating_states": [
        "id",
        "equipment_id",
        "operating_state_id",
        "started_at",
        "ended_at",
        "source_system",
        "source_record_id",
    ],
    "sensors": [
        "id",
        "equipment_id",
        "component_id",
        "canonical_id",
        "tag_name",
        "name",
        "sensor_type",
        "engineering_unit",
        "status",
        "source_system",
        "source_record_id",
    ],
    "observations": [
        "id",
        "sensor_id",
        "observed_at",
        "value",
        "engineering_unit",
        "quality",
        "source_record_id",
        "ingested_at",
    ],
    "alarms": [
        "id",
        "sensor_id",
        "canonical_id",
        "alarm_code",
        "alarm_type",
        "severity",
        "status",
        "message",
        "triggered_at",
        "cleared_at",
        "source_system",
        "source_record_id",
    ],
    "symptoms": ["id", "canonical_id", "code", "name", "description"],
    "failure_modes": ["id", "canonical_id", "code", "name", "description"],
    "causes": ["id", "canonical_id", "code", "name", "category", "description"],
    "failure_events": [
        "id",
        "equipment_id",
        "component_id",
        "canonical_id",
        "event_number",
        "title",
        "description",
        "started_at",
        "ended_at",
        "downtime_minutes",
        "status",
        "source_system",
        "source_record_id",
    ],
    "failure_event_symptoms": [
        "failure_event_id",
        "symptom_id",
        "observed_at",
        "severity",
    ],
    "failure_event_failure_modes": [
        "failure_event_id",
        "failure_mode_id",
        "confidence",
        "is_primary",
    ],
    "failure_event_causes": [
        "id",
        "failure_event_id",
        "cause_id",
        "verification_method",
        "verified_at",
        "verified_by",
        "is_primary",
    ],
    "damages": [
        "id",
        "failure_event_id",
        "component_id",
        "damage_type",
        "description",
        "severity",
        "detected_at",
    ],
    "alarm_symptoms": ["alarm_id", "symptom_id"],
    "alarm_failure_events": ["alarm_id", "failure_event_id", "relationship_type"],
    "technicians": ["id", "canonical_id", "employee_number", "name", "specialization", "status"],
    "spare_parts": ["id", "canonical_id", "part_number", "name", "manufacturer", "description"],
    "work_orders": [
        "id",
        "equipment_id",
        "canonical_id",
        "work_order_number",
        "work_order_type",
        "priority",
        "status",
        "description",
        "opened_at",
        "scheduled_start_at",
        "completed_at",
        "source_system",
        "source_record_id",
    ],
    "maintenance_activities": [
        "id",
        "work_order_id",
        "activity_code",
        "activity_type",
        "sequence_number",
        "description",
        "status",
        "started_at",
        "completed_at",
        "result",
        "source_system",
        "source_record_id",
    ],
    "activity_technicians": ["activity_id", "technician_id", "role"],
    "activity_spare_parts": ["activity_id", "spare_part_id", "quantity", "unit"],
    "activity_targets": ["id", "activity_id", "equipment_id", "component_id"],
    "work_order_failure_events": ["work_order_id", "failure_event_id", "relationship_type"],
}


def _stable_uuid(seed: int, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{seed}:{key}"))


def generate_asset_dataset(seed: int = DEFAULT_SEED) -> dict[str, list[dict[str, Any]]]:
    """Generate the asset foundation portion of the 1x dataset."""
    rng = random.Random(seed)
    generated_at = "2026-01-01T00:00:00+00:00"
    plant_id = _stable_uuid(seed, "plant:REFINERY-01")

    dataset: dict[str, list[dict[str, Any]]] = {
        "plants": [
            {
                "id": plant_id,
                "canonical_id": "PLANT-REFINERY-01",
                "code": "REFINERY-01",
                "name": "Synthetic Refinery Plant",
                "description": "Cloud-agnostic learning dataset",
            }
        ],
        "production_lines": [],
        "equipment": [],
        "components": [],
        "asset_identifiers": [],
    }

    manufacturers = [("Flowserve", "HPX"), ("Sulzer", "AHLSTAR"), ("KSB", "CPK")]
    component_specs = [
        ("BRG-DE", "Drive End Bearing", "bearing"),
        ("BRG-NDE", "Non-Drive End Bearing", "bearing"),
        ("SEAL", "Mechanical Seal", "mechanical_seal"),
        ("IMP", "Impeller", "impeller"),
    ]

    for line_number in range(1, 3):
        line_code = f"PROCESS-{line_number:02d}"
        line_id = _stable_uuid(seed, f"line:{line_code}")
        dataset["production_lines"].append(
            {
                "id": line_id,
                "plant_id": plant_id,
                "canonical_id": f"LINE-{line_code}",
                "code": line_code,
                "name": f"Process Line {line_number}",
                "description": "Synthetic process line",
            }
        )

        for pump_number in range(1, 4):
            tag_number = f"P-{line_number}{pump_number:02d}"
            equipment_id = _stable_uuid(seed, f"equipment:{tag_number}")
            manufacturer, model = rng.choice(manufacturers)
            dataset["equipment"].append(
                {
                    "id": equipment_id,
                    "production_line_id": line_id,
                    "canonical_id": f"EQUIPMENT-{tag_number}",
                    "tag_number": tag_number,
                    "name": f"Centrifugal Pump {tag_number}",
                    "equipment_type": "centrifugal_pump",
                    "manufacturer": manufacturer,
                    "model": model,
                    "serial_number": f"SN-{line_number}{pump_number:02d}-{seed}",
                    "commissioned_at": f"20{15 + line_number}-{pump_number:02d}-01",
                    "status": "active",
                }
            )

            for source_system, identifier_type, prefix, is_primary in (
                ("cmms", "equipment_number", "EQ", True),
                ("pi_af", "element_path", "PI-AF", False),
            ):
                dataset["asset_identifiers"].append(
                    {
                        "id": _stable_uuid(seed, f"identifier:{source_system}:{tag_number}"),
                        "equipment_id": equipment_id,
                        "component_id": "",
                        "source_system": source_system,
                        "identifier_type": identifier_type,
                        "identifier_value": f"{prefix}-{tag_number}",
                        "is_primary": str(is_primary).lower(),
                        "source_updated_at": generated_at,
                        "ingested_at": generated_at,
                    }
                )

            for suffix, name, component_type in component_specs:
                component_tag = f"{tag_number}-{suffix}"
                dataset["components"].append(
                    {
                        "id": _stable_uuid(seed, f"component:{component_tag}"),
                        "equipment_id": equipment_id,
                        "canonical_id": f"COMPONENT-{component_tag}",
                        "tag_number": component_tag,
                        "name": name,
                        "component_type": component_type,
                        "manufacturer": manufacturer,
                        "model": "SYNTHETIC-COMPONENT",
                        "serial_number": f"CSN-{component_tag}",
                        "status": "active",
                    }
                )

    return dataset


def generate_synthetic_dataset(seed: int = DEFAULT_SEED) -> dict[str, list[dict[str, Any]]]:
    """Generate asset, sensor, observation, alarm, and operating-state data."""
    dataset = generate_asset_dataset(seed)
    start_at = datetime(2026, 1, 1, tzinfo=UTC)
    ingested_at = datetime(2026, 1, 3, tzinfo=UTC).isoformat()

    state_specs = [
        ("running", "Running", "Equipment operating at steady state"),
        ("startup", "Startup", "Equipment transitioning to running state"),
        ("idle", "Idle", "Equipment available but not running"),
    ]
    dataset["operating_states"] = [
        {
            "id": _stable_uuid(seed, f"operating-state:{code}"),
            "canonical_id": f"OPERATING-STATE-{code.upper()}",
            "code": code,
            "name": name,
            "description": description,
        }
        for code, name, description in state_specs
    ]
    state_ids = {row["code"]: row["id"] for row in dataset["operating_states"]}
    dataset["equipment_operating_states"] = []
    dataset["sensors"] = []
    dataset["observations"] = []
    dataset["alarms"] = []

    components_by_equipment: dict[str, list[dict[str, Any]]] = {}
    for component in dataset["components"]:
        components_by_equipment.setdefault(component["equipment_id"], []).append(component)

    intervals = [("running", 0, 24), ("startup", 24, 26), ("running", 26, 48)]
    sensor_specs = [
        ("vibration", "mm/s", "BRG-DE", 2.4, 8.2, 7.0),
        ("temperature", "degC", None, 58.0, 92.0, 85.0),
    ]

    for equipment in dataset["equipment"]:
        equipment_id = equipment["id"]
        tag_number = equipment["tag_number"]

        for interval_index, (state_code, start_hour, end_hour) in enumerate(intervals):
            interval_start = start_at + timedelta(hours=start_hour)
            interval_end = start_at + timedelta(hours=end_hour)
            dataset["equipment_operating_states"].append(
                {
                    "id": _stable_uuid(seed, f"state-interval:{tag_number}:{interval_index}"),
                    "equipment_id": equipment_id,
                    "operating_state_id": state_ids[state_code],
                    "started_at": interval_start.isoformat(),
                    "ended_at": interval_end.isoformat(),
                    "source_system": "pi_historian",
                    "source_record_id": f"PI-STATE-{tag_number}-{interval_index:02d}",
                }
            )

        for sensor_type, unit, component_suffix, baseline, peak, threshold in sensor_specs:
            component_id = ""
            equipment_target_id = equipment_id
            if component_suffix:
                component = next(
                    row
                    for row in components_by_equipment[equipment_id]
                    if row["tag_number"].endswith(component_suffix)
                )
                component_id = component["id"]
                equipment_target_id = ""

            sensor_tag = f"{tag_number}-{sensor_type.upper()}"
            sensor_id = _stable_uuid(seed, f"sensor:{sensor_tag}")
            dataset["sensors"].append(
                {
                    "id": sensor_id,
                    "equipment_id": equipment_target_id,
                    "component_id": component_id,
                    "canonical_id": f"SENSOR-{sensor_tag}",
                    "tag_name": sensor_tag,
                    "name": f"{sensor_type.title()} Sensor {tag_number}",
                    "sensor_type": sensor_type,
                    "engineering_unit": unit,
                    "status": "active",
                    "source_system": "pi_historian",
                    "source_record_id": f"PI-TAG-{sensor_tag}",
                }
            )

            for hour in range(48):
                observed_at = start_at + timedelta(hours=hour)
                if 34 <= hour <= 38:
                    value = peak - abs(36 - hour) * (peak - threshold) / 3
                else:
                    variation = ((hour + int(tag_number[-1])) % 7 - 3) * 0.03
                    value = baseline * (1 + variation)
                dataset["observations"].append(
                    {
                        "id": _stable_uuid(seed, f"observation:{sensor_tag}:{hour}"),
                        "sensor_id": sensor_id,
                        "observed_at": observed_at.isoformat(),
                        "value": f"{value:.6f}",
                        "engineering_unit": unit,
                        "quality": "good",
                        "source_record_id": f"PI-OBS-{sensor_tag}-{hour:03d}",
                        "ingested_at": ingested_at,
                    }
                )

            triggered_at = start_at + timedelta(hours=36)
            cleared_at = start_at + timedelta(hours=39)
            dataset["alarms"].append(
                {
                    "id": _stable_uuid(seed, f"alarm:{sensor_tag}:36"),
                    "sensor_id": sensor_id,
                    "canonical_id": f"ALARM-{sensor_tag}-20260102T120000Z",
                    "alarm_code": f"{sensor_type.upper()}_HIGH",
                    "alarm_type": "high_threshold",
                    "severity": "high",
                    "status": "cleared",
                    "message": f"{sensor_type.title()} exceeded {threshold:g} {unit}",
                    "triggered_at": triggered_at.isoformat(),
                    "cleared_at": cleared_at.isoformat(),
                    "source_system": "pi_historian",
                    "source_record_id": f"PI-ALARM-{sensor_tag}-036",
                }
            )

    _add_reliability_scenarios(dataset, seed, start_at)
    _add_maintenance_scenarios(dataset, seed)

    return dataset


def _add_reliability_scenarios(
    dataset: dict[str, list[dict[str, Any]]], seed: int, start_at: datetime
) -> None:
    vocabulary = {
        "symptoms": [
            ("high_vibration", "High Vibration", "Vibration exceeds normal operating limit"),
            ("overheating", "Overheating", "Temperature exceeds normal operating limit"),
        ],
        "failure_modes": [
            ("bearing_failure", "Bearing Failure", "Bearing can no longer support rotation"),
            ("seal_failure", "Seal Failure", "Mechanical seal loses containment"),
            (
                "impeller_degradation",
                "Impeller Degradation",
                "Impeller loses hydraulic performance",
            ),
        ],
        "causes": [
            (
                "lubricant_contamination",
                "Lubricant Contamination",
                "lubrication",
                "Foreign material contaminated bearing lubricant",
            ),
            (
                "seal_face_wear",
                "Seal Face Wear",
                "mechanical",
                "Progressive wear reduced seal face integrity",
            ),
            (
                "cavitation",
                "Cavitation",
                "process",
                "Insufficient suction pressure generated vapor bubbles",
            ),
        ],
    }
    dataset["symptoms"] = [
        {
            "id": _stable_uuid(seed, f"symptom:{code}"),
            "canonical_id": f"SYMPTOM-{code.upper()}",
            "code": code,
            "name": name,
            "description": description,
        }
        for code, name, description in vocabulary["symptoms"]
    ]
    dataset["failure_modes"] = [
        {
            "id": _stable_uuid(seed, f"failure-mode:{code}"),
            "canonical_id": f"FAILURE-MODE-{code.upper()}",
            "code": code,
            "name": name,
            "description": description,
        }
        for code, name, description in vocabulary["failure_modes"]
    ]
    dataset["causes"] = [
        {
            "id": _stable_uuid(seed, f"cause:{code}"),
            "canonical_id": f"CAUSE-{code.upper()}",
            "code": code,
            "name": name,
            "category": category,
            "description": description,
        }
        for code, name, category, description in vocabulary["causes"]
    ]
    symptom_ids = {row["code"]: row["id"] for row in dataset["symptoms"]}
    mode_ids = {row["code"]: row["id"] for row in dataset["failure_modes"]}
    cause_ids = {row["code"]: row["id"] for row in dataset["causes"]}
    dataset["failure_events"] = []
    dataset["failure_event_symptoms"] = []
    dataset["failure_event_failure_modes"] = []
    dataset["failure_event_causes"] = []
    dataset["damages"] = []
    dataset["alarm_symptoms"] = []
    dataset["alarm_failure_events"] = []

    scenario_specs = [
        ("BRG-DE", "bearing_failure", "lubricant_contamination", "bearing_wear"),
        ("SEAL", "seal_failure", "seal_face_wear", "seal_face_damage"),
        ("IMP", "impeller_degradation", "cavitation", "impeller_erosion"),
    ]
    components_by_equipment = {
        equipment["id"]: [
            component
            for component in dataset["components"]
            if component["equipment_id"] == equipment["id"]
        ]
        for equipment in dataset["equipment"]
    }
    sensors_by_id = {row["id"]: row for row in dataset["sensors"]}
    failure_started_at = start_at + timedelta(hours=38)
    failure_ended_at = start_at + timedelta(hours=42)

    for index, equipment in enumerate(dataset["equipment"]):
        tag_number = equipment["tag_number"]
        component_suffix, mode_code, cause_code, damage_type = scenario_specs[index % 3]
        component = next(
            row
            for row in components_by_equipment[equipment["id"]]
            if row["tag_number"].endswith(component_suffix)
        )
        event_number = f"FE-2026-{index + 1:04d}"
        failure_id = _stable_uuid(seed, f"failure-event:{event_number}")
        dataset["failure_events"].append(
            {
                "id": failure_id,
                "equipment_id": equipment["id"],
                "component_id": component["id"],
                "canonical_id": f"FAILURE-{event_number}",
                "event_number": event_number,
                "title": f"{mode_code.replace('_', ' ').title()} on {tag_number}",
                "description": "Synthetic verified reliability scenario",
                "started_at": failure_started_at.isoformat(),
                "ended_at": failure_ended_at.isoformat(),
                "downtime_minutes": 240,
                "status": "closed",
                "source_system": "cmms",
                "source_record_id": f"NOTIF-{index + 1:06d}",
            }
        )
        for symptom_code in ("high_vibration", "overheating"):
            dataset["failure_event_symptoms"].append(
                {
                    "failure_event_id": failure_id,
                    "symptom_id": symptom_ids[symptom_code],
                    "observed_at": failure_started_at.isoformat(),
                    "severity": "high",
                }
            )
        dataset["failure_event_failure_modes"].append(
            {
                "failure_event_id": failure_id,
                "failure_mode_id": mode_ids[mode_code],
                "confidence": "1.0000",
                "is_primary": "true",
            }
        )
        dataset["failure_event_causes"].append(
            {
                "id": _stable_uuid(seed, f"verified-cause:{event_number}:{cause_code}"),
                "failure_event_id": failure_id,
                "cause_id": cause_ids[cause_code],
                "verification_method": "root_cause_analysis",
                "verified_at": (failure_ended_at + timedelta(hours=24)).isoformat(),
                "verified_by": "Reliability Engineer",
                "is_primary": "true",
            }
        )
        dataset["damages"].append(
            {
                "id": _stable_uuid(seed, f"damage:{event_number}:{damage_type}"),
                "failure_event_id": failure_id,
                "component_id": component["id"],
                "damage_type": damage_type,
                "description": f"Verified {damage_type.replace('_', ' ')}",
                "severity": "high",
                "detected_at": failure_started_at.isoformat(),
            }
        )

        equipment_sensor_ids = {
            row["id"]
            for row in dataset["sensors"]
            if row["equipment_id"] == equipment["id"]
            or row["component_id"]
            in {item["id"] for item in components_by_equipment[equipment["id"]]}
        }
        for alarm in dataset["alarms"]:
            if alarm["sensor_id"] not in equipment_sensor_ids:
                continue
            sensor_type = sensors_by_id[alarm["sensor_id"]]["sensor_type"]
            symptom_code = "high_vibration" if sensor_type == "vibration" else "overheating"
            dataset["alarm_symptoms"].append(
                {"alarm_id": alarm["id"], "symptom_id": symptom_ids[symptom_code]}
            )
            dataset["alarm_failure_events"].append(
                {
                    "alarm_id": alarm["id"],
                    "failure_event_id": failure_id,
                    "relationship_type": "preceded",
                }
            )


def _add_maintenance_scenarios(dataset: dict[str, list[dict[str, Any]]], seed: int) -> None:
    technician_specs = [
        ("T-001", "Ayu Pratama", "mechanical inspection"),
        ("T-002", "Bima Santoso", "rotating equipment"),
        ("T-003", "Citra Lestari", "condition monitoring"),
    ]
    part_specs = [
        ("BRG-KIT-6208", "Bearing Replacement Kit", "bearing_wear"),
        ("SEAL-KIT-M01", "Mechanical Seal Kit", "seal_face_damage"),
        ("IMP-CP-01", "Centrifugal Pump Impeller", "impeller_erosion"),
    ]
    dataset["technicians"] = [
        {
            "id": _stable_uuid(seed, f"technician:{employee_number}"),
            "canonical_id": f"TECHNICIAN-{employee_number}",
            "employee_number": employee_number,
            "name": name,
            "specialization": specialization,
            "status": "active",
        }
        for employee_number, name, specialization in technician_specs
    ]
    dataset["spare_parts"] = [
        {
            "id": _stable_uuid(seed, f"spare-part:{part_number}"),
            "canonical_id": f"SPARE-PART-{part_number}",
            "part_number": part_number,
            "name": name,
            "manufacturer": "Synthetic Parts Co.",
            "description": f"Replacement material for {damage_type.replace('_', ' ')}",
        }
        for part_number, name, damage_type in part_specs
    ]
    parts_by_damage = {
        damage_type: next(
            row for row in dataset["spare_parts"] if row["part_number"] == part_number
        )
        for part_number, _, damage_type in part_specs
    }
    dataset["work_orders"] = []
    dataset["maintenance_activities"] = []
    dataset["activity_technicians"] = []
    dataset["activity_spare_parts"] = []
    dataset["activity_targets"] = []
    dataset["work_order_failure_events"] = []
    damages_by_failure = {row["failure_event_id"]: row for row in dataset["damages"]}

    activity_specs = [
        ("INSPECT", "inspection", 0, 45, "Damage confirmed during visual inspection"),
        ("REPAIR", "repair", 45, 180, "Damaged component replaced and aligned"),
        ("TEST", "functional_test", 180, 225, "Functional test passed within normal limits"),
    ]
    for index, failure in enumerate(dataset["failure_events"]):
        work_order_number = f"WO-2026-{index + 1:04d}"
        work_order_id = _stable_uuid(seed, f"work-order:{work_order_number}")
        opened_at = datetime.fromisoformat(failure["started_at"])
        completed_at = datetime.fromisoformat(failure["ended_at"])
        damage = damages_by_failure[failure["id"]]
        dataset["work_orders"].append(
            {
                "id": work_order_id,
                "equipment_id": failure["equipment_id"],
                "canonical_id": f"WORK-ORDER-{work_order_number}",
                "work_order_number": work_order_number,
                "work_order_type": "corrective",
                "priority": "high",
                "status": "completed",
                "description": f"Corrective response for {failure['event_number']}",
                "opened_at": opened_at.isoformat(),
                "scheduled_start_at": (opened_at + timedelta(minutes=15)).isoformat(),
                "completed_at": completed_at.isoformat(),
                "source_system": "cmms",
                "source_record_id": f"WO-{index + 1:06d}",
            }
        )
        dataset["work_order_failure_events"].append(
            {
                "work_order_id": work_order_id,
                "failure_event_id": failure["id"],
                "relationship_type": "responds_to",
            }
        )

        for sequence, (code, activity_type, start_minute, end_minute, result) in enumerate(
            activity_specs, start=1
        ):
            activity_id = _stable_uuid(seed, f"activity:{work_order_number}:{sequence}")
            dataset["maintenance_activities"].append(
                {
                    "id": activity_id,
                    "work_order_id": work_order_id,
                    "activity_code": code,
                    "activity_type": activity_type,
                    "sequence_number": sequence,
                    "description": f"{activity_type.replace('_', ' ').title()} affected component",
                    "status": "completed",
                    "started_at": (opened_at + timedelta(minutes=start_minute)).isoformat(),
                    "completed_at": (opened_at + timedelta(minutes=end_minute)).isoformat(),
                    "result": result,
                    "source_system": "cmms",
                    "source_record_id": f"WO-{index + 1:06d}-OP-{sequence:02d}",
                }
            )
            technician = dataset["technicians"][(index + sequence - 1) % len(technician_specs)]
            dataset["activity_technicians"].append(
                {
                    "activity_id": activity_id,
                    "technician_id": technician["id"],
                    "role": "lead" if sequence == 2 else "executor",
                }
            )
            dataset["activity_targets"].append(
                {
                    "id": _stable_uuid(seed, f"activity-target:{activity_id}"),
                    "activity_id": activity_id,
                    "equipment_id": "",
                    "component_id": damage["component_id"],
                }
            )
            if activity_type == "repair":
                part = parts_by_damage[damage["damage_type"]]
                dataset["activity_spare_parts"].append(
                    {
                        "activity_id": activity_id,
                        "spare_part_id": part["id"],
                        "quantity": "1.000",
                        "unit": "each",
                    }
                )


def generate_technician_notes(
    dataset: dict[str, list[dict[str, Any]]], seed: int = DEFAULT_SEED
) -> list[dict[str, Any]]:
    equipment = {row["id"]: row for row in dataset["equipment"]}
    failures = {row["id"]: row for row in dataset["failure_events"]}
    causes = {row["id"]: row for row in dataset["causes"]}
    verified_causes = {row["failure_event_id"]: row for row in dataset["failure_event_causes"]}
    links = {
        row["work_order_id"]: row["failure_event_id"]
        for row in dataset["work_order_failure_events"]
    }
    notes = []

    for work_order in dataset["work_orders"]:
        failure = failures[links[work_order["id"]]]
        asset = equipment[failure["equipment_id"]]
        cause = causes[verified_causes[failure["id"]]["cause_id"]]
        phrase = {
            "lubricant_contamination": (
                "dark particles in the bearing grease suggest lubricant contamination"
            ),
            "seal_face_wear": "scoring on the seal faces suggests progressive seal face wear",
            "cavitation": "pitting on the impeller suggests prolonged cavitation",
        }[cause["code"]]
        text = (
            f"Technician note for {asset['tag_number']}. High vibration and temperature were "
            f"observed before shutdown. Inspection found that {phrase}. The damaged component "
            "was replaced, alignment checked, and the functional test passed."
        )
        notes.append(
            {
                "note_id": _stable_uuid(seed, f"technician-note:{work_order['work_order_number']}"),
                "work_order_number": work_order["work_order_number"],
                "failure_event_number": failure["event_number"],
                "equipment_tag": asset["tag_number"],
                "text": text,
                "ground_truth": {
                    "equipment_canonical_id": asset["canonical_id"],
                    "probable_cause_code": cause["code"],
                    "cause_phrase": phrase,
                },
            }
        )
    return notes


def write_csv_dataset(dataset: dict[str, list[dict[str, Any]]], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files = []
    for table_name, rows in dataset.items():
        output_path = output_dir / f"{table_name}.csv"
        with output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FIELD_ORDER[table_name])
            writer.writeheader()
            writer.writerows(rows)
        written_files.append(output_path)
    return written_files


def write_jsonl(rows: Iterable[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, sort_keys=True) + "\n")
    return output_path


def _row_count_lines(dataset: dict[str, Iterable[dict[str, Any]]]) -> Iterable[str]:
    for table_name, rows in dataset.items():
        yield f"{table_name}: {len(list(rows))} rows"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic manufacturing 1x dataset")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=Path("data/generated/1x"))
    args = parser.parse_args()

    dataset = generate_synthetic_dataset(args.seed)
    from app.synthetic.validation import validate_dataset

    validate_dataset(dataset)
    write_csv_dataset(dataset, args.output)
    notes = generate_technician_notes(dataset, args.seed)
    write_jsonl(notes, args.output / "technician_notes.jsonl")
    print("\n".join(_row_count_lines(dataset)))
    print(f"technician_notes: {len(notes)} rows")


if __name__ == "__main__":
    main()
