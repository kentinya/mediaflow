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


def reject_retired_configuration_input(document: object, *, baseline: object = None) -> None:
    """Reject a retired spelling in newly submitted configuration.

    ``baseline`` is the exact document the submission is derived from (the
    current Draft for an edit, the Active base for validation/activation, or
    ``None`` for an import).  It is used only to recognise an unchanged
    historical object; it never supplies values to the submitted document.
    """

    if not isinstance(document, Mapping):
        return
    base = baseline if isinstance(baseline, Mapping) else {}

    _reject_authority(document, base)

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
                raise ValueError("automation.schedules is retired; use automationTaskDefinitions")

    notifications = document.get("notifications")
    if isinstance(notifications, Mapping) and "webhooks" in notifications:
        base_notifications = base.get("notifications")
        base_notifications = base_notifications if isinstance(base_notifications, Mapping) else {}
        if notifications.get("webhooks") != base_notifications.get("webhooks"):
            raise ValueError("notifications.webhooks is retired; use the root webhooks section")

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
    _reject_webhook_events(document, base)


def _reject_authority(document: Mapping[str, Any], baseline: Mapping[str, Any]) -> None:
    api = document.get("api")
    if not isinstance(api, Mapping):
        return
    if "tokenEnv" in api:
        raise ValueError(
            "api.tokenEnv is retired; remove it from the submitted configuration. "
            "Web accounts and server-side sessions authenticate every current entry"
        )
    if "principals" not in api:
        return
    base_api = baseline.get("api")
    base_api = base_api if isinstance(base_api, Mapping) else {}
    # An immutable historical Active carries the deployment authority it was
    # published with. Carrying that exact object forward unchanged stays valid
    # for read compatibility, but a new submission may not introduce, edit or
    # keep an independently supplied principal list: current deployments
    # create Web accounts through the host one-time setup code.
    if isinstance(base_api, Mapping) and _principal_identity(
        api.get("principals")
    ) == _principal_identity(base_api.get("principals")):
        return
    raise ValueError(
        "api.principals is retired; remove it from the submitted configuration. "
        "Create the first administrator through the Web sign-in page with a "
        "one-time code from `mediaflow accounts issue-setup-code`"
    )


def _principal_identity(value: object):
    """The deployment-authority identity of one principal list.

    A stored first-setup document may spell the default ``enabled: true``
    explicitly while the bootstrap object omits it. That is the same authority,
    not a new principal declaration, so the comparison uses only the stable
    identity fields and the effective enabled state.
    """

    if not isinstance(value, list):
        return None
    identity = []
    for item in value:
        if not isinstance(item, Mapping):
            return value
        identity.append(
            (
                item.get("id"),
                item.get("tokenEnv"),
                tuple(item.get("roles", ())),
                bool(item.get("enabled", True)),
            )
        )
    return tuple(identity)


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


def _reject_classification_fields(document: Mapping[str, Any], base: Mapping[str, Any]) -> None:
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
            if "destinationContract" in (result if isinstance(result, Mapping) else {}) and (
                previous is None or rule != previous
            ):
                raise ValueError(
                    f"classification rule {rule.get('id', '?')}.result.destinationContract "
                    "is a read-only projection, not configuration input"
                )
            if not _is_current_classification_rule(rule) and (previous is None or rule != previous):
                raise ValueError(
                    f"classification rule {rule.get('id', '?')} uses the retired flat shape; "
                    "use conditions and result objects"
                )


def _is_current_classification_rule(rule: Mapping[str, Any]) -> bool:
    return isinstance(rule.get("conditions"), Mapping) and isinstance(rule.get("result"), Mapping)


def _webhook_sections(document: Mapping[str, Any]):
    """Yield every Webhook item list in one document, current spelling first."""

    root = document.get("webhooks")
    if isinstance(root, list):
        yield root
    notifications = document.get("notifications")
    if isinstance(notifications, Mapping):
        nested = notifications.get("webhooks")
        if isinstance(nested, list):
            yield nested


def _reject_webhook_events(document: Mapping[str, Any], base: Mapping[str, Any]) -> None:
    accepted = {
        str(item.get("id")): item
        for section in _webhook_sections(base)
        for item in section
        if isinstance(item, Mapping)
    }
    for section in _webhook_sections(document):
        for webhook in section:
            if not isinstance(webhook, Mapping):
                continue
            events = webhook.get("events")
            if not isinstance(events, list) or not any(
                isinstance(event, str) and event.startswith("job.") for event in events
            ):
                continue
            # An accepted definition that is carried forward unchanged keeps
            # its Task lifecycle meaning when the Active snapshot is read; only
            # a submitted change has to adopt the current event names.
            if accepted.get(str(webhook.get("id"))) == webhook:
                continue
            raise ValueError(
                f"Webhook {webhook.get('id', '?')} uses a retired job.* event; "
                "use task.completed, task.failed, task.cancelled or schedule.emitted"
            )


def _paired_objects(document: Mapping[str, Any], base: Mapping[str, Any], section: str):
    previous = {
        str(item.get("id")): item for item in _list(base.get(section)) if isinstance(item, Mapping)
    }
    for item in _list(document.get(section)):
        if isinstance(item, Mapping):
            yield item, previous.get(str(item.get("id")))


def _list(value: object) -> list:
    return copy.deepcopy(value) if isinstance(value, list) else []


__all__ = ["reject_retired_configuration_input"]
