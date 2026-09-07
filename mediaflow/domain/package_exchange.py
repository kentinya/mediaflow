from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime

from mediaflow.domain.manual_safety import (
    contains_manual_secret,
    redact_evidence_text,
    redact_evidence_value,
)
from mediaflow.domain.notification import (
    redact_webhook_urls,
    unsafe_webhook_url_items,
)
from mediaflow.domain.task_persistence import PersistentResultRecord, redact_persistent_result

CONFIGURATION_PACKAGE_KIND = "mediaflow.configuration.v1"
RESULT_PACKAGE_KIND = "mediaflow.results.v1"
CONFIGURATION_PACKAGE_SCHEMA_VERSION = 1
RESULT_PACKAGE_SCHEMA_VERSION = 1
MAX_CONFIGURATION_PACKAGE_BYTES = 1_500_000
MAX_RESULT_EXPORT_LIMIT = 500
REDACTION_EVIDENCE_LIMIT = 256

_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENVIRONMENT_SUFFIX = re.compile(r"(?i)(?:env|environment)$")
_SECRET_FIELD_NAME = re.compile(
    r"(?i)(?:secret|token|password|passwd|api[_-]?key|access[_-]?key|session[_-]?token"
    r"|authorization|cookie|username)"
)


class PackageExchangeError(RuntimeError):
    """A bounded, operator-facing package import/export failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int,
        durable_state: str,
        retry_safe: bool = True,
        next_action: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = str(message)
        self.code = code
        self.status = status
        self.durable_state = durable_state
        self.retry_safe = retry_safe
        self.next_action = next_action
        self.details = dict(details or {})

    def document(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "durableState": self.durable_state,
            "sideEffects": "none",
            "retrySafe": self.retry_safe,
            "nextAction": self.next_action,
            **self.details,
        }


def canonical_digest(value: object) -> str:
    """Return a deterministic SHA-256 digest for JSON-compatible package payloads."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def bounded_json_size(value: object, *, maximum: int) -> int:
    """Validate and return the UTF-8 size of a canonical JSON value."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    size = len(encoded.encode("utf-8"))
    if size > maximum:
        raise PackageExchangeError(
            "package payload is too large",
            code="package_too_large",
            status=422,
            durable_state="no_configuration_or_result_changed",
            next_action="export a smaller bounded package scope",
        )
    return size


def _is_secret_field_name(key: object) -> bool:
    if not isinstance(key, str):
        return False
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    if normalized in {
        "token",
        "password",
        "passwd",
        "secret",
        "accesskey",
        "accesskeyid",
        "secretaccesskey",
        "sessiontoken",
        "authorization",
        "cookie",
        "apikey",
        "api key",
        "username",
    }:
        return True
    return bool(_SECRET_FIELD_NAME.search(key))


def _is_environment_reference_field(key: object) -> bool:
    return (
        isinstance(key, str)
        and bool(_ENVIRONMENT_SUFFIX.search(key))
        and bool(_SECRET_FIELD_NAME.search(key))
    )


def _valid_environment_name(value: object) -> bool:
    return isinstance(value, str) and bool(_ENVIRONMENT_NAME.fullmatch(value))


def redact_configuration_document(
    document: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Return an export-safe document plus bounded redaction evidence.

    Deployment-owned ``*Env`` fields remain environment-variable references.
    Literal secret fields and text-shaped credentials are removed/redacted and
    listed in evidence so operators can inspect exactly what was changed.
    """

    evidence: list[dict[str, object]] = []

    def redact(value: object, path: str) -> object:
        if isinstance(value, dict):
            result: dict[str, object] = {}
            for key, child in value.items():
                field = f"{path}.{key}" if path else str(key)
                if _is_environment_reference_field(key):
                    if _valid_environment_name(child):
                        result[key] = child
                        evidence.append(
                            {
                                "field": field,
                                "kind": "environment_reference",
                                "environmentVariable": child,
                                "ownership": "deployment_environment",
                            }
                        )
                    else:
                        result[key] = "***REDACTED***"
                        evidence.append(
                            {
                                "field": field,
                                "kind": "redacted_invalid_reference",
                                "environmentVariable": None,
                                "ownership": "deployment_environment",
                            }
                        )
                elif _is_secret_field_name(key):
                    result[key] = "***REDACTED***"
                    evidence.append({"field": field, "kind": "redacted_literal"})
                elif isinstance(child, str):
                    before = child
                    after = redact_evidence_text(before)
                    result[key] = after
                    if after != before:
                        evidence.append(
                            {
                                "field": field,
                                "kind": "redacted_text",
                                "textSnippet": before[:24] if before else "",
                            }
                        )
                else:
                    result[key] = redact(child, field)
            return result
        if isinstance(value, list):
            return [redact(child, f"{path}[{index}]") for index, child in enumerate(value)]
        if isinstance(value, str):
            return redact_evidence_text(value)
        return copy.deepcopy(value)

    working = copy.deepcopy(document)
    unsafe_webhooks = unsafe_webhook_url_items(working)
    redact_webhook_urls(working)
    for identifier, _url in unsafe_webhooks:
        evidence.append(
            {
                "field": f"webhooks.{identifier}.url" if identifier else "webhooks.url",
                "kind": "redacted_webhook_url",
                "webhookId": identifier or None,
            }
        )
    safe = redact(working, "")
    if not isinstance(safe, dict):
        raise PackageExchangeError(
            "configuration package document must be an object",
            code="invalid_schema",
            status=422,
            durable_state="no_configuration_changed",
            next_action="export a supported managed configuration revision",
        )
    if len(evidence) > REDACTION_EVIDENCE_LIMIT:
        evidence = evidence[:REDACTION_EVIDENCE_LIMIT]
    return safe, evidence


def package_secret_issues(document: object) -> list[dict[str, object]]:
    """Find literal/unsafe secret content in an incoming configuration payload."""

    issues: list[dict[str, object]] = []

    if isinstance(document, dict):
        for identifier, _url in unsafe_webhook_url_items(document):
            issues.append(
                {
                    "field": f"webhooks.{identifier}.url" if identifier else "webhooks.url",
                    "kind": "webhook_url_credential",
                }
            )

    def inspect(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                field = f"{path}.{key}" if path else str(key)
                if _is_environment_reference_field(key):
                    if not _valid_environment_name(child):
                        issues.append(
                            {
                                "field": field,
                                "kind": "invalid_secret_reference",
                            }
                        )
                elif _is_secret_field_name(key):
                    issues.append({"field": field, "kind": "literal_secret_field"})
                elif isinstance(child, str) and contains_manual_secret(child):
                    issues.append({"field": field, "kind": "literal_secret_text"})
                else:
                    inspect(child, field)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                inspect(child, f"{path}[{index}]")
        elif isinstance(value, str) and contains_manual_secret(value):
            issues.append({"field": path, "kind": "literal_secret_text"})

    inspect(document, "configuration")
    return issues


def _producer() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    try:
        application_version = version("mediaflow")
    except PackageNotFoundError:
        application_version = "development"
    return {"id": "mediaflow", "version": application_version}


def build_configuration_package(
    revision,
    active,
    *,
    generated_at: datetime,
) -> dict[str, object]:
    """Build one bounded, secret-free configuration package for a revision."""

    safe_document, redaction_evidence = redact_configuration_document(revision.document)
    document_digest = canonical_digest(safe_document)
    payload = {
        "schemaVersion": revision.schema_version,
        "revisionDigest": revision.digest,
        "documentDigest": document_digest,
        "document": safe_document,
    }
    source = {
        "revisionId": revision.revision_id,
        "revisionSequence": revision.revision_sequence,
        "version": revision.version,
        "status": revision.status.value,
        "digest": revision.digest,
        "baseActiveRevisionId": revision.base_active_revision_id,
        "createdAt": revision.created_at.isoformat(),
        "updatedAt": revision.updated_at.isoformat(),
    }
    current_active = active
    currentness = {
        "currentActiveRevisionId": current_active.revision_id if current_active else None,
        "currentActiveVersion": (current_active.revision_sequence if current_active else None),
        "currentActiveDigest": current_active.digest if current_active else None,
        "sourceIsCurrent": bool(
            current_active is not None and current_active.revision_id == revision.revision_id
        ),
        "authority": "MANAGED" if current_active else "NONE",
    }
    package = {
        "packageKind": CONFIGURATION_PACKAGE_KIND,
        "packageSchemaVersion": CONFIGURATION_PACKAGE_SCHEMA_VERSION,
        "packageVersion": 1,
        "generatedAt": generated_at.isoformat(),
        "producer": _producer(),
        "source": source,
        "currentness": currentness,
        "validation": {
            "status": revision.status.value,
            "validationErrors": list(revision.validation_errors),
            "validatedAt": (revision.validated_at.isoformat() if revision.validated_at else None),
            "managedDocumentSchemaVersion": revision.schema_version,
            "packageSchemaVersion": CONFIGURATION_PACKAGE_SCHEMA_VERSION,
        },
        "redaction": {
            "scope": "managed_configuration_revision_document",
            "entries": redaction_evidence,
            "entryCount": len(redaction_evidence),
        },
        "payload": payload,
    }
    bounded_json_size(payload, maximum=MAX_CONFIGURATION_PACKAGE_BYTES)
    package["packageDigest"] = canonical_digest(payload)
    return package


def validate_configuration_package(value: object) -> dict[str, object]:
    """Validate one supported configuration package and return its parsed fields."""

    if not isinstance(value, dict):
        raise PackageExchangeError(
            "configuration package must be a JSON object",
            code="invalid_schema",
            status=422,
            durable_state="no_configuration_changed",
            next_action="import a supported MediaFlow configuration package",
        )
    if value.get("packageKind") != CONFIGURATION_PACKAGE_KIND:
        raise PackageExchangeError(
            "unsupported configuration package kind",
            code="unsupported_package_version",
            status=422,
            durable_state="no_configuration_changed",
            next_action="use a package exported by this MediaFlow version",
        )
    schema = value.get("packageSchemaVersion")
    try:
        schema_value = int(schema)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        schema_value = -1
    if schema_value != CONFIGURATION_PACKAGE_SCHEMA_VERSION:
        raise PackageExchangeError(
            "unsupported configuration package schema version",
            code="unsupported_package_version",
            status=422,
            durable_state="no_configuration_changed",
            next_action="export a current supported configuration package and retry",
        )
    package_version = value.get("packageVersion")
    try:
        package_value = int(package_version)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        package_value = -1
    if package_value != 1:
        raise PackageExchangeError(
            "unsupported configuration package version",
            code="unsupported_package_version",
            status=422,
            durable_state="no_configuration_changed",
            next_action="export a current supported configuration package and retry",
        )
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise PackageExchangeError(
            "configuration package payload is missing",
            code="invalid_schema",
            status=422,
            durable_state="no_configuration_changed",
            next_action="import an unmodified MediaFlow configuration package",
        )
    document = payload.get("document")
    if not isinstance(document, dict):
        raise PackageExchangeError(
            "configuration package document must be an object",
            code="invalid_schema",
            status=422,
            durable_state="no_configuration_changed",
            next_action="import an unmodified MediaFlow configuration package",
        )
    try:
        bounded_json_size(document, maximum=1024 * 1024)
    except PackageExchangeError as error:
        raise PackageExchangeError(
            "configuration package document is too large",
            code="package_too_large",
            status=422,
            durable_state="no_configuration_changed",
            next_action="reduce the configuration scope and retry",
        ) from error
    supplied_document_digest = payload.get("documentDigest")
    if not isinstance(supplied_document_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", supplied_document_digest
    ):
        raise PackageExchangeError(
            "configuration package document digest is malformed",
            code="invalid_digest",
            status=422,
            durable_state="no_configuration_changed",
            next_action="import an unmodified MediaFlow configuration package",
        )
    if canonical_digest(document) != supplied_document_digest:
        raise PackageExchangeError(
            "configuration package document digest does not match its payload",
            code="digest_mismatch",
            status=422,
            durable_state="no_configuration_changed",
            next_action="do not edit package digests; export a fresh package",
        )
    package_digest = value.get("packageDigest")
    if not isinstance(package_digest, str) or canonical_digest(payload) != package_digest:
        raise PackageExchangeError(
            "configuration package digest does not match its payload",
            code="digest_mismatch",
            status=422,
            durable_state="no_configuration_changed",
            next_action="do not edit package digests; export a fresh package",
        )
    issues = package_secret_issues(document)
    if issues:
        raise PackageExchangeError(
            "configuration package contains literal secret material",
            code="literal_secret_rejected",
            status=422,
            durable_state="no_configuration_changed",
            next_action="replace literal credentials with deployment-owned environment references",
            details={
                "issues": issues[:64],
                "issueCount": len(issues),
            },
        )
    source = value.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("revisionId"), str):
        raise PackageExchangeError(
            "configuration package source is missing",
            code="invalid_schema",
            status=422,
            durable_state="no_configuration_changed",
            next_action="import an unmodified MediaFlow configuration package",
        )
    currentness = value.get("currentness")
    if not isinstance(currentness, dict) or not isinstance(
        currentness.get("currentActiveRevisionId"), str
    ):
        raise PackageExchangeError(
            "configuration package currentness evidence is missing",
            code="invalid_schema",
            status=422,
            durable_state="no_configuration_changed",
            next_action="import an unmodified MediaFlow configuration package",
        )
    return {
        "source": source,
        "currentness": currentness,
        "validation": value.get("validation", {}),
        "document": document,
        "documentDigest": supplied_document_digest,
        "packageDigest": package_digest,
    }


def result_item_document(result: PersistentResultRecord) -> dict[str, object]:
    """Project one durable Result into a bounded, secret-free export row."""

    safe = redact_persistent_result(result, redact_identity=False)
    return {
        "resultId": safe.result_id,
        "taskId": safe.task_id,
        "itemId": safe.item_id,
        "sourceStorageId": safe.source_storage_id,
        "sourcePath": safe.source_path,
        "destinationStorageId": safe.destination_storage_id,
        "destinationPath": safe.destination_path,
        "recognitionType": safe.recognition_type,
        "provider": safe.provider,
        "providerId": safe.provider_id,
        "metadataPolicyId": safe.metadata_policy_id,
        "namingPolicyId": safe.naming_policy_id,
        "classificationPolicyId": safe.classification_policy_id,
        "organizePolicyId": safe.organize_policy_id,
        "operation": safe.operation,
        "status": safe.status,
        "createdAt": safe.created_at.isoformat(),
        "title": safe.title,
        "error": safe.error,
        "completedOperations": list(safe.completed_operations),
        "attachmentCount": safe.attachment_count,
        "retryAttempts": safe.retry_attempts,
        "retryCategory": safe.retry_category,
        "cleanupStatus": safe.cleanup_status,
        "cleanupStepCount": safe.cleanup_step_count,
        "effectCertainty": safe.effect_certainty,
        "uncertainEffects": list(safe.uncertain_effects),
        "sourceOccurrenceId": safe.source_occurrence_id,
        "sourceFingerprint": safe.source_fingerprint,
        "sourceFingerprintState": safe.source_fingerprint_state,
    }


def redact_result_rows(
    results: tuple[PersistentResultRecord, ...] | list[PersistentResultRecord],
) -> list[dict[str, object]]:
    """Apply secret-free result projection to every row."""

    return [result_item_document(result) for result in results]


def result_redaction_entries(
    results: tuple[PersistentResultRecord, ...] | list[PersistentResultRecord],
) -> list[dict[str, object]]:
    """Report which persisted Result text fields needed redaction."""

    entries: list[dict[str, object]] = []
    comparable = (
        "title",
        "error",
        "completed_operations",
        "uncertain_effects",
    )
    for index, result in enumerate(results):
        safe = redact_persistent_result(result)
        for name in comparable:
            raw = getattr(result, name)
            value = getattr(safe, name)
            if raw != value:
                entries.append(
                    {
                        "field": f"results[{index}].{name}",
                        "kind": "redacted_text",
                    }
                )
    return entries[:REDACTION_EVIDENCE_LIMIT]


def package_redaction_sweep(value: object) -> object:
    """Final belt-and-braces redaction before any package leaves the boundary."""

    return redact_evidence_value(value)
