import unittest

from mediaflow.domain.library import MediaLibrary, ResourceLibrary
from mediaflow.domain.metadata import MediaIdentity, MediaType
from mediaflow.domain.organizer import ConflictStrategy, OrganizeOperationType, OrganizePolicy
from mediaflow.domain.parser import FileContext, ParseResult
from mediaflow.domain.storage import StorageCapabilities
from mediaflow.domain.tasks import Task, TaskStatus


class DomainModelTest(unittest.TestCase):
    def test_core_models_can_be_created_with_safe_defaults(self) -> None:
        resource = ResourceLibrary("downloads", "Downloads", "local", "/Downloads")
        media = MediaLibrary("main", "Main", "local", "/Media")
        context = FileContext("local", resource.library_id, "Movie.mkv", "Movie.mkv")
        parsed = ParseResult("Movie", year=2025)
        identity = MediaIdentity("fixture", "1", MediaType.MOVIE, "Movie", year=2025)
        task = Task("task-1", "organize")
        policy = OrganizePolicy("move", OrganizeOperationType.MOVE)

        self.assertEqual("local", media.storage_id)
        self.assertEqual("Movie.mkv", context.filename)
        self.assertEqual(2025, parsed.year)
        self.assertEqual("1", identity.provider_id)
        self.assertEqual(TaskStatus.PENDING, task.status)
        self.assertEqual(ConflictStrategy.MANUAL, policy.conflict_strategy)

    def test_storage_capabilities_default_to_unsupported(self) -> None:
        capabilities = StorageCapabilities()
        self.assertFalse(capabilities.can_move)
        self.assertFalse(capabilities.can_copy)
        self.assertFalse(capabilities.can_delete)
        self.assertFalse(capabilities.can_hard_link)
        self.assertFalse(capabilities.can_soft_link)
