"""Focused Task 45.5 coverage: exact durable scope resolution.

The paused-run recovery boundary resolves a Task's durable ``scope_path``
against the *pinned* runtime's ResourceLibrary roots.  These cases pin the
contract that only an explicitly absent scope means "unspecified": a real path
is preserved byte-for-byte, so a directory name that ends (or begins) with a
space, a whitespace-only component, a Unicode or long name, and an absolute
display path can never silently resolve to a different neighbouring directory.

They exercise the pure resolver directly, with no Storage, Provider, Task or
repository, exactly as the recovery boundary does.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from mediaflow.application.task_scope import (
    ScopeResolutionError,
    resolve_resource_library_scope,
)


@dataclass(frozen=True)
class _Library:
    library_id: str
    root_path: str
    enabled: bool = True


@dataclass(frozen=True)
class _Runtime:
    resource_libraries: tuple[_Library, ...]
    resource_display_roots: tuple[tuple[str, str], ...] = ()


class UnspecifiedScopeTests(unittest.TestCase):
    def test_none_and_exact_empty_select_the_only_enabled_library(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        for scope in (None, ""):
            with self.subTest(scope=scope):
                library, relative = resolve_resource_library_scope(runtime, scope)
                self.assertEqual(library.library_id, "source")
                self.assertEqual(relative, "")

    def test_multiple_libraries_leave_an_unspecified_scope_unresolved(self) -> None:
        runtime = _Runtime((_Library("a", "one"), _Library("b", "two")))
        with self.assertRaises(ScopeResolutionError) as raised:
            resolve_resource_library_scope(runtime, None)
        self.assertEqual(raised.exception.reason, "scope_unresolved")

    def test_a_whitespace_only_scope_is_not_an_unspecified_scope(self) -> None:
        # A whitespace-only string is a real (if unusual) relative path, not the
        # documented "unspecified" form, so it must be refused rather than
        # widened into the whole library.
        runtime = _Runtime((_Library("source", "media"),))
        with self.assertRaises(ScopeResolutionError) as raised:
            resolve_resource_library_scope(runtime, "   ")
        self.assertEqual(raised.exception.reason, "scope_unresolved")


class RelativeScopeTests(unittest.TestCase):
    def test_trailing_space_directory_is_preserved(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        library, relative = resolve_resource_library_scope(runtime, "media/Incoming/Folder ")
        self.assertEqual(library.library_id, "source")
        self.assertEqual(relative, "Incoming/Folder ")

    def test_leading_space_directory_is_preserved(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        _library, relative = resolve_resource_library_scope(runtime, "media/Incoming/ Folder")
        self.assertEqual(relative, "Incoming/ Folder")

    def test_whitespace_only_component_is_preserved(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        _library, relative = resolve_resource_library_scope(runtime, "media/Incoming/   ")
        self.assertEqual(relative, "Incoming/   ")

    def test_unicode_and_long_names_are_preserved(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        long_name = "剧集 " + "x" * 200
        _library, relative = resolve_resource_library_scope(runtime, f"media/Incoming/{long_name}")
        self.assertEqual(relative, f"Incoming/{long_name}")

    def test_a_bare_relative_scope_without_the_root_is_refused(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        with self.assertRaises(ScopeResolutionError) as raised:
            resolve_resource_library_scope(runtime, "Incoming/Folder ")
        self.assertEqual(raised.exception.reason, "scope_unresolved")

    def test_an_escaping_scope_is_refused(self) -> None:
        runtime = _Runtime((_Library("source", "media"),))
        with self.assertRaises(ScopeResolutionError) as raised:
            resolve_resource_library_scope(runtime, "media/../secret")
        self.assertEqual(raised.exception.reason, "invalid_path")


class DisplayRootScopeTests(unittest.TestCase):
    def test_absolute_display_path_preserves_the_exact_trailing_space_directory(self) -> None:
        runtime = _Runtime(
            (_Library("source", "media"),),
            (("source", "/mnt/library"),),
        )
        _library, relative = resolve_resource_library_scope(
            runtime, "/mnt/library/Incoming/Folder "
        )
        self.assertEqual(relative, "Incoming/Folder ")

    def test_absolute_display_path_to_a_sibling_is_not_confused(self) -> None:
        # Two real directories differ only by a trailing space.  Each absolute
        # path resolves to its own exact directory; neither collapses onto the
        # other.
        runtime = _Runtime(
            (_Library("source", "media"),),
            (("source", "/mnt/library"),),
        )
        _left, left = resolve_resource_library_scope(runtime, "/mnt/library/Incoming/Folder ")
        _right, right = resolve_resource_library_scope(runtime, "/mnt/library/Incoming/Folder")
        self.assertEqual(left, "Incoming/Folder ")
        self.assertEqual(right, "Incoming/Folder")

    def test_the_display_root_itself_resolves_to_the_library_root(self) -> None:
        runtime = _Runtime(
            (_Library("source", "media"),),
            (("source", "/mnt/library"),),
        )
        library, relative = resolve_resource_library_scope(runtime, "/mnt/library")
        self.assertEqual(library.library_id, "source")
        self.assertEqual(relative, "")


class AmbiguityTests(unittest.TestCase):
    def test_a_scope_claimed_by_two_libraries_is_refused(self) -> None:
        runtime = _Runtime(
            (_Library("a", "media"), _Library("b", "media")),
            (),
        )
        with self.assertRaises(ScopeResolutionError) as raised:
            resolve_resource_library_scope(runtime, "media/Incoming/Folder ")
        self.assertEqual(raised.exception.reason, "scope_unresolved")

    def test_a_disabled_library_is_unavailable(self) -> None:
        runtime = _Runtime(
            (_Library("source", "media", enabled=False),),
            (("source", "/mnt/library"),),
        )
        with self.assertRaises(ScopeResolutionError) as raised:
            resolve_resource_library_scope(runtime, "/mnt/library/Incoming")
        self.assertEqual(raised.exception.reason, "resource_library_not_found")


if __name__ == "__main__":
    unittest.main()
