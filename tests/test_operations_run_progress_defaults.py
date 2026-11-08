"""The progress snapshot's read-only defaults must construct on every declared Python.

Python 3.11 rejects a ``MappingProxyType`` instance used directly as a dataclass
field default, so the three count mappings need a factory. Each snapshot must
still receive its own read-only mapping: one run's progress can never share or
mutate another's counts.
"""

from __future__ import annotations

import unittest
from dataclasses import MISSING, fields
from types import MappingProxyType

from mediaflow.domain.operations_run import OperationsRunProgress

COUNT_FIELDS = ("dispositions", "effect_counts", "scan_progress")


class OperationsRunProgressDefaultsTests(unittest.TestCase):
    def test_defaults_are_read_only_and_per_instance(self) -> None:
        first = OperationsRunProgress(available=True)
        second = OperationsRunProgress(available=False)
        for name in COUNT_FIELDS:
            value = getattr(first, name)
            self.assertEqual(dict(value), {})
            self.assertIsInstance(value, MappingProxyType)
            with self.assertRaises(TypeError):
                value["item"] = 1  # type: ignore[index]
            other = getattr(second, name)
            self.assertIsNot(value, other)
            self.assertEqual(other, value)
        self.assertFalse(second.available)

    def test_declared_count_defaults_use_a_factory(self) -> None:
        declared = {definition.name: definition for definition in fields(OperationsRunProgress)}
        for name in COUNT_FIELDS:
            self.assertIsNot(
                declared[name].default_factory,
                MISSING,
                f"{name} needs a factory default: a mappingproxy instance is "
                "rejected on Python 3.11",
            )


if __name__ == "__main__":
    unittest.main()
