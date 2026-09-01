"""Application facade for managed Automation Task Definition edits.

The underlying persistence and optimistic Draft lifecycle remain owned by
``ConfigurationObjectService``.  This narrow facade gives API, Web and other
adapters a name that reflects the business object without introducing a second
definition store or execution pipeline.
"""

from mediaflow.application.configuration_objects import ConfigurationObjectService


class AutomationTaskDefinitionService(ConfigurationObjectService):
    """Managed Automation Task Definition operations backed by one Draft."""

    def create(self, revision_id, definition, *, expected_version, actor):
        return self.create_automation_task_definition(
            revision_id,
            definition,
            expected_version=expected_version,
            actor=actor,
        )

    def edit(self, revision_id, definition_id, definition, *, expected_version, actor):
        return self.edit_automation_task_definition(
            revision_id,
            definition_id,
            definition,
            expected_version=expected_version,
            actor=actor,
        )

    def copy(self, revision_id, definition_id, *, expected_version, actor, new_id=None, name=None):
        return self.copy_automation_task_definition(
            revision_id,
            object_id=definition_id,
            new_object_id=new_id,
            new_name=name,
            expected_version=expected_version,
            actor=actor,
        )

    def enable(self, revision_id, definition_id, *, expected_version, actor):
        return self.enable_automation_task_definition(
            revision_id,
            definition_id,
            expected_version=expected_version,
            actor=actor,
        )

    def disable(self, revision_id, definition_id, *, expected_version, actor):
        return self.disable_automation_task_definition(
            revision_id,
            definition_id,
            expected_version=expected_version,
            actor=actor,
        )


__all__ = ["AutomationTaskDefinitionService"]
