"""Entités désactivées par défaut : diagnostic (sauf Jours de fonctionnement),
Plages horaires, Localiser (LED) et Débit fixe (radon).

Vérification statique (module `ast`) des déclarations des plateformes, pour ne pas nécessiter d'installer `homeassistant`.
Lancer avec : python3 -m unittest discover -s tests
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

_COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "vmi_plus"

# Champs de diagnostic qui restent activés par défaut.
ENABLED_DIAGNOSTIC_FIELDS = {"operating_days"}


def _is_diagnostic(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "DIAGNOSTIC"
        and isinstance(node.value, ast.Name)
        and node.value.id == "EntityCategory"
    )


def _class_attrs(cls: ast.ClassDef) -> dict[str, ast.AST]:
    attrs = {}
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    attrs[target.id] = stmt.value
    return attrs


def _parse(name: str) -> ast.Module:
    return ast.parse((_COMPONENT / name).read_text(encoding="utf-8"))


class SensorDefaultsTests(unittest.TestCase):
    def _sensor_calls(self) -> list[ast.Call]:
        return [
            node
            for node in ast.walk(_parse("sensor.py"))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "VmiPlusSensor"
        ]

    def test_diagnostic_sensors_disabled_except_operating_days(self) -> None:
        calls = self._sensor_calls()
        self.assertGreater(len(calls), 5)
        seen_diagnostic = set()
        for call in calls:
            field = call.args[3].value  # (device, entry, telemetry_type, field, ...)
            diagnostic = any(_is_diagnostic(arg) for arg in call.args) or any(
                kw.arg == "entity_category" and _is_diagnostic(kw.value)
                for kw in call.keywords
            )
            enabled = {
                kw.arg: kw.value.value
                for kw in call.keywords
                if kw.arg == "enabled_default" and isinstance(kw.value, ast.Constant)
            }.get("enabled_default")
            with self.subTest(field=field):
                if field in ENABLED_DIAGNOSTIC_FIELDS:
                    self.assertTrue(diagnostic)
                    self.assertIs(enabled, True)
                elif diagnostic:
                    seen_diagnostic.add(field)
                    # Pas de surcharge : la valeur par défaut (désactivé) s'applique.
                    self.assertIsNot(enabled, True)
                else:
                    self.assertIsNot(enabled, False)
        self.assertTrue(
            {"software_version", "volume", "surface", "preheat_type", "position"}
            <= seen_diagnostic
        )

    def test_default_derived_from_entity_category(self) -> None:
        source = (_COMPONENT / "sensor.py").read_text(encoding="utf-8")
        self.assertIn(
            "enabled_default = entity_category is not EntityCategory.DIAGNOSTIC", source
        )
        self.assertIn(
            "self._attr_entity_registry_enabled_default = enabled_default", source
        )


class DiagnosticClassesTests(unittest.TestCase):
    def test_diagnostic_classes_disabled_by_default(self) -> None:
        checked = []
        for module in ("sensor.py", "binary_sensor.py"):
            for node in ast.walk(_parse(module)):
                if not isinstance(node, ast.ClassDef):
                    continue
                attrs = _class_attrs(node)
                category = attrs.get("_attr_entity_category")
                if category is None or not _is_diagnostic(category):
                    continue
                checked.append(node.name)
                with self.subTest(cls=node.name):
                    enabled = attrs.get("_attr_entity_registry_enabled_default")
                    self.assertIsInstance(enabled, ast.Constant)
                    self.assertIs(enabled.value, False)
        self.assertEqual(
            sorted(checked),
            [
                "VmiPlusFlagBinarySensor",
                "VmiPlusSelfTestBinarySensor",
                "VmiPlusSensorsListSensor",
            ],
        )


# Entités non diagnostic désactivées par défaut, par plateforme : clé passée
# au constructeur (et donc à l'unique_id).
DISABLED_KEYS = {
    ("switch.py", "VmiPlusSwitch"): {"fixed_flow", "time_slots"},
    ("button.py", "VmiPlusButton"): {"locate"},
}


class OptionalEntitiesTests(unittest.TestCase):
    def _calls(self, module: str, cls: str) -> dict[str, ast.Call]:
        calls = {}
        for node in ast.walk(_parse(module)):
            if not isinstance(node, ast.Call) or len(node.args) < 3:
                continue
            func = node.func
            # Appel direct `VmiPlusSwitch(...)` ou `super().__init__(...)` d'une sous-classe.
            direct = isinstance(func, ast.Name) and func.id == cls
            via_super = (
                isinstance(func, ast.Attribute)
                and func.attr == "__init__"
                and isinstance(func.value, ast.Call)
                and isinstance(func.value.func, ast.Name)
                and func.value.func.id == "super"
            )
            if (direct or via_super) and isinstance(node.args[2], ast.Constant):
                key = node.args[2].value
                if isinstance(key, str):
                    calls[key] = node
        return calls

    def test_optional_entities_disabled(self) -> None:
        for (module, cls), disabled in DISABLED_KEYS.items():
            calls = self._calls(module, cls)
            self.assertTrue(disabled <= set(calls), (module, sorted(calls)))
            for key, call in calls.items():
                enabled = next(
                    (
                        kw.value.value
                        for kw in call.keywords
                        if kw.arg == "enabled_default" and isinstance(kw.value, ast.Constant)
                    ),
                    None,
                )
                with self.subTest(module=module, key=key):
                    if key in disabled:
                        self.assertIs(enabled, False)
                    else:
                        self.assertIsNot(enabled, False)

    def test_constructor_applies_enabled_default(self) -> None:
        for module in ("switch.py", "button.py"):
            with self.subTest(module=module):
                source = (_COMPONENT / module).read_text(encoding="utf-8")
                self.assertIn("enabled_default: bool = True", source)
                self.assertIn(
                    "self._attr_entity_registry_enabled_default = enabled_default", source
                )


if __name__ == "__main__":
    unittest.main()
