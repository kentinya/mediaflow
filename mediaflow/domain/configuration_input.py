"""Current configuration-input rules for newly submitted documents.

A managed revision is immutable: a document that was accepted before this
module existed keeps being readable through the historical loader.  A *new*
submission, however, must use the current spelling.  This boundary rejects the
retired spellings that used to be silently accepted or ignored, while allowing
an unchanged historical object to travel through an unrelated edit so the
operator's existing destination, rule or pin is not rewritten by a cosmetic
save.

The rule is deliberately object-scoped:

* a legacy object that is byte-for-byte the same as the object in the supplied
  baseline is historical data being carried forward;
* a new object, or any changed object, may not contain a retired field;
* authority fields (``api.tokenEnv``) are never carried into a new submission,
  because that would mint an implicit administrator.

Only pure input parsing lives here.  It never reads the database, constructs a
Storage/Provider, validates references or writes anything.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

#: Provider connection fields that used to live directly on a Storage object.
#: ``storages[*].options`` is the current location.
_STORAGE_OPTION_FIELDS = frozenset(
    {
        "tokenEnv",
        "baseUrl",
        "usernameEnv",
        "passwordEnv",
        "host",
        "share",
        "domain",
        "port",
        "operationTimeout",
        "accessKeyEnv",
        "secretKeyEnv",
        "sessionTokenEnv",
        "bucket",
        "endpoint",
        "region",
        "forcePathStyle",
        "connectTimeout",
        "requestTimeout",
        "maxConcurrency",
        "maxRetries",
        "pageSize",
        "multipartThreshold",
        "multipartPartSize",
    }
)

_NAMING_LEGACY_FIELDS = frozenset(
    {
        "movieDirectoryTemplate",
        "movieFileTemplate",
        "tvSeriesDirectoryTemplate",
        "tvSeasonDirectoryTemplate",
        "tvEpisodeFileTemplate",
    }
)

_CLASSIFICATION_LEGACY_RESULT_FIELDS = frozenset({"library", "category", "subcategory"})


def reject_retired_configuration_input(
    document: object, *, baseline: object = None
) -> None:
    """Reject a retired spelling in newly submitted configuration.

    ``baseline`` is the exact document the submission is derived from (the
    current Draft for an edit, the Active base for validation/activation, or
    ``None`` for an import).  It is used only to recognise an unchanged
    historical object; it never supplies values to the submitted document.
    """

    if not isinstance(document, Mapping):
        return
    base = baseline if isinstance(baseline, Mapping) else {}

    _reject_authority(document)

    automation = document.get("automation")
    if isinstance(automation, Mapping):
        base_automation = base.get("automation")
        base_automation = base_automation if isinstance(base_automation, Mapping) else {}
        for field in ("taskDefinitions", "staleJobAgeSeconds", "schedules"):
            if field in automation and automation.get(field) != base_automation.get(field):
                if field == "taskDefinitions":
                    raise ValueError(
                        "automation.taskDefinitions is retired; use the root "
                        "automationTaskDefinitions section"
                    )
                if field == "staleJobAgeSeconds":
                    raise ValueError(
                        "automation.staleJobAgeSeconds is retired and has no replacement setting"
                    )
                raise ValueError(
                    "automation.schedules is retired; use automationTaskDefinitions"
                )

    notifications = document.get("notifications")
    if isinstance(notifications, Mapping) and "webhooks" in notifications:
        base_notifications = base.get("notifications")
        base_notifications = (
            base_notifications if isinstance(base_notifications, Mapping) else {}
        )
        if notifications.get("webhooks") != base_notifications.get("webhooks"):
            raise ValueError(
                "notifications.webhooks is retired; use the root webhooks section"
            )

    _reject_storage_fields(document, base)
    _reject_simple_section_fields(
        document,
        base,
        section="resourceLibraries",
        fields={"rootPath": "displayRootPath (display) and storagePath (Storage-relative)"},
    )
    _reject_simple_section_fields(
        document,
        base,
        section="metadataPolicies",
        fields={"mediaType": "mediaQueryType"},
    )
    _reject_simple_section_fields(
        document,
        base,
        section="organizePolicies",
        fields={"overwrite": "conflictStrategy"},
    )
    _reject_simple_section_fields(
        document,
        base,
        section="namingPolicies",
        fields={field: field for field in _NAMING_LEGACY_FIELDS},
    )
    _reject_classification_fields(document, base)
    _reject_webhook_events(document)


def _reject_authority(document: Mapping[str, Any]) -> None:
    api = document.get("api")
    if isinstance(api, Mapping) and "tokenEnv" in api:
        raise ValueError(
            "api.tokenEnv is retired and cannot grant an implicit administrator; "
            "declare api.principals with explicit roles instead"
        )
    for index, principal in enumerate(
        api.get("principals", ()) if isinstance(api, Mapping) else ()
    ):
        if isinstance(principal, Mapping) and any(
            field in principal for field in ("token", "secret", "password", "authorization")
        ):
            raise ValueError(
                f"api.principals[{index}] must reference an environment variable, "
                "not a literal credential"
            )


def _reject_storage_fields(document: Mapping[str, Any], base: Mapping[str, Any]) -> None:
    for item, previous in _paired_objects(document, base, "storages"):
        legacy = _STORAGE_OPTION_FIELDS.intersection(item)
        if legacy and (previous is None or item != previous):
            raise ValueError(
                f"storages[{item.get('id', '?')}].{sorted(legacy)[0]} is retired; "
                "put provider connection fields under Storage.options"
            )


def _reject_simple_section_fields(
    document: Mapping[str, Any],
    base: Mapping[str, Any],
    *,
    section: str,
    fields: Mapping[str, str],
) -> None:
    for item, previous in _paired_objects(document, base, section):
        present = fields.keys() & item.keys()
        if present and (previous is None or item != previous):
            field = sorted(present)[0]
            raise ValueError(
                f"{section}[{item.get('id', '?')}].{field} is retired; use {fields[field]}"
            )


def _reject_classification_fields(
    document: Mapping[str, Any], base: Mapping[str, Any]
) -> None:
    base_policies = {
        str(item.get("id")): item
        for item in _list(base.get("classificationPolicies"))
        if isinstance(item, Mapping)
    }
    for policy in _list(document.get("classificationPolicies")):
        if not isinstance(policy, Mapping):
            continue
        previous_policy = base_policies.get(str(policy.get("id")))
        previous_rules = {
            str(item.get("id")): item
            for item in _list(
                previous_policy.get("rules") if isinstance(previous_policy, Mapping) else ()
            )
            if isinstance(item, Mapping)
        }
        rules = policy.get("rules")
        if not isinstance(rules, list):
            raise ValueError(
                f"classificationPolicies[{policy.get('id', '?')}].rules must be an array"
            )
        for rule in rules:
            if not isinstance(rule, Mapping):
                raise ValueError(
                    f"classificationPolicies[{policy.get('id', '?')}].rules must contain objects"
                )
            previous = previous_rules.get(str(rule.get("id")))
            result = rule.get("result")
            legacy_result = (
                _CLASSIFICATION_LEGACY_RESULT_FIELDS.intersection(result)
                if isinstance(result, Mapping)
                else set()
            )
            if legacy_result and (previous is None or rule != previous):
                field = sorted(legacy_result)[0]
                raise ValueError(
                    f"classification rule {rule.get('id', '?')}.result.{field} is retired; "
                    "express the complete destination as mediaLibraryId plus path"
                )
            if "destinationContract" in (
                result if isinstance(result, Mapping) else {}
            ) and (previous is None or rule != previous):
                raise ValueError(
                    f"classification rule {rule.get('id', '?')}.result.destinationContract "
                    "is a read-only projection, not configuration input"
                )
            if not _is_current_classification_rule(rule) and (
                previous is None or rule != previous
            ):
                raise ValueError(
                    f"classification rule {rule.get('id', '?')} uses the retired flat shape; "
                    "use conditions and result objects"
                )


def _is_current_classification_rule(rule: Mapping[str, Any]) -> bool:
    return isinstance(rule.get("conditions"), Mapping) and isinstance(
        rule.get("result"), Mapping
    )


def _reject_webhook_events(document: Mapping[str, Any]) -> None:
    webhooks = document.get("webhooks")
    if not isinstance(webhooks, list):
        notifications = document.get("notifications")
        webhooks = (
            notifications.get("webhooks") if isinstance(notifications, Mapping) else ()
        )
    for webhook in _list(webhooks):
        if not isinstance(webhook, Mapping):
            continue
        events = webhook.get("events")
        if isinstance(events, list) and any(
            isinstance(event, str) and event.startswith("job.") for event in events
        ):
            raise ValueError(
                f"Webhook {webhook.get('id', '?')} uses a retired job.* event; "
                "use task.completed, task.failed, task.cancelled or schedule.emitted"
            )


def _paired_objects(
    document: Mapping[str, Any], base: Mapping[str, Any], section: str
):
    previous = {
        str(item.get("id")): item
        for item in _list(base.get(section))
        if isinstance(item, Mapping)
    }
    for item in _list(document.get(section)):
        if isinstance(item, Mapping):
            yield item, previous.get(str(item.get("id")))


def _list(value: object) -> list:
    return copy.deepcopy(value) if isinstance(value, list) else []


__all__ = ["reject_retired_configuration_input"]
