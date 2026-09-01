"""Compatibility import surface for the managed Automation Task Definition contract."""

from mediaflow.domain.automation import (
    AutomationRunMode,
    AutomationTaskDefinition,
    AutomationTaskDefinitionMode,
    AutomationTaskRunMode,
    parse_automation_task_definition,
)

__all__ = [
    "AutomationRunMode",
    "AutomationTaskDefinition",
    "AutomationTaskDefinitionMode",
    "AutomationTaskRunMode",
    "parse_automation_task_definition",
]
