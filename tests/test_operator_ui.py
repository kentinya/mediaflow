from __future__ import annotations

import io
import json
import unittest

from mediaflow.domain.security import ApiPermission, ResolvedApiPrincipal
from mediaflow.interfaces.operator_ui import APP_JS, INDEX_HTML, STYLE_CSS
from mediaflow.interfaces.service_api import MediaFlowApi


class ExplodingRepository:
    def __getattr__(self, name):
        raise AssertionError(f"static UI must not access repository method {name}")


def request(api, path: str, method: str = "GET"):
    status = []
    headers = []
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(),
    }

    def start_response(value, values):
        status.append(value)
        headers.extend(values)

    body = b"".join(api(environ, start_response))
    return int(status[0].split()[0]), dict(headers), body


def _js_function_body(script: str, name: str) -> str:
    """Return one JS function body from the served asset by brace matching."""

    opening = script.index("{", script.index(f"function {name}("))
    return _js_braced_body(script, opening)


def _js_braced_body(script: str, opening: int) -> str:
    """Return the body whose opening brace is at ``opening``."""

    depth = 0
    for index in range(opening, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[opening + 1 : index]
    raise AssertionError("JavaScript block has an unbalanced body")


class OperatorUiTests(unittest.TestCase):
    def setUp(self) -> None:
        principal = ResolvedApiPrincipal("viewer", "unused-token", frozenset({ApiPermission.READ}))
        self.api = MediaFlowApi(ExplodingRepository(), None, principals=(principal,))

    def test_static_routes_are_public_read_only_and_hardened(self) -> None:
        expected = {
            "/ui": ("text/html; charset=utf-8", INDEX_HTML),
            "/ui/": ("text/html; charset=utf-8", INDEX_HTML),
            "/ui/app.js": ("text/javascript; charset=utf-8", APP_JS),
            "/ui/style.css": ("text/css; charset=utf-8", STYLE_CSS),
        }
        for path, (content_type, body) in expected.items():
            with self.subTest(path=path):
                status, headers, actual = request(self.api, path)
                self.assertEqual(status, 200)
                self.assertEqual(actual, body)
                self.assertEqual(headers["Content-Type"], content_type)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        status, _, document = request(self.api, "/ui/app.js", "POST")
        self.assertEqual(status, 405)
        self.assertEqual(json.loads(document)["error"]["code"], "method_not_allowed")

    def test_assets_are_self_contained_and_credentials_are_memory_only(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        combined = html + script + STYLE_CSS.decode()
        self.assertNotIn("http://", combined)
        self.assertNotIn("https://", combined)
        self.assertNotIn("local" + "Storage", script)
        self.assertNotIn("session" + "Storage", script)
        self.assertNotIn("document." + "cookie", script)
        self.assertNotIn("innerHTML", script)
        self.assertIn("textContent", script)
        self.assertIn('type="password"', html)
        self.assertIn("tokenInput.value = ''", script)
        self.assertIn("token = ''", script)
        self.assertIn("'Authorization': `Bearer ${token}`", script)

    def test_dashboard_and_review_requests_are_bounded(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        self.assertIn('data-view="files"', html)
        self.assertIn("/api/v1/dashboard?recentLimit=10", script)
        self.assertIn("?status=pending&limit=100", script)
        self.assertIn("?limit=100", script)
        self.assertIn("/api/v1/files?", script)
        self.assertIn("limit=100", script)
        self.assertIn("showDetail('files'", script)
        self.assertIn("resourceLibrary", script)
        self.assertIn("recognitionType", script)
        self.assertIn("providerId", script)
        self.assertIn("scanStatus", script)
        self.assertIn("renderFileReMatchForm", script)
        self.assertIn("metadata-reviews", script)
        self.assertIn("classification-reviews", script)
        self.assertIn("encodeURIComponent(id)", script)

    def test_scheduler_and_notification_views_are_bounded_and_read_only(self) -> None:
        html = INDEX_HTML.decode()
        script = APP_JS.decode()
        self.assertIn('data-view="schedules"', html)
        self.assertIn('data-view="notifications"', html)
        self.assertIn("/api/v1/schedules", script)
        self.assertIn("/audit?limit=100", script)
        self.assertIn("/api/v1/notifications?limit=100&status=", script)
        self.assertIn("Refresh notifications", script)
        self.assertIn("showScheduleAudit(id, data.previous_cursor)", script)
        self.assertIn("showScheduleAudit(id, data.next_cursor)", script)
        self.assertIn("renderNotifications(status, data.previous_cursor)", script)
        self.assertIn("renderNotifications(status, data.next_cursor)", script)
        self.assertIn("renderNotifications(selector.value)", script)
        self.assertIn(
            "['all', 'pending', 'delivering', 'retry', 'delivered', 'dead-letter']", script
        )
        self.assertIn("failureCategory", script)
        self.assertNotIn("notification-worker", script)
        self.assertNotIn("notifications/requeue", script)
        self.assertNotIn("scheduler tick", script)
        self.assertNotIn("webhook" + "Url", script)
        self.assertNotIn("signature", script.lower())

    def test_ui_generates_only_existing_safe_decision_shapes(self) -> None:
        script = APP_JS.decode()
        self.assertIn("['skip', 'rename']", script)
        self.assertIn("{strategy}", script)
        self.assertIn("'candidateRank'", script)
        self.assertIn("'choiceRank'", script)
        conflict_actions = _js_function_body(script, "renderConflictActions")
        self.assertNotIn("overwrite", conflict_actions.lower())
        # Overwrite may only be displayed, never requested: no served path sends the field.
        self.assertNotIn("overwrite:", script)
        self.assertNotIn("overwrite=true", script)
        self.assertIn("Queue DryRun job", script)
        self.assertIn("'/api/v1/jobs', {method: 'POST'", script)
        self.assertNotIn("/api/v1/tasks/${encodeURIComponent(id)}/resume", script)
        self.assertIn("Admitted recovery request", script)
        self.assertIn("request.actor", script)
        self.assertIn("Recovery continuation", script)
        self.assertIn("confirmRecoveryContinuation", script)
        self.assertIn("DRY_RUN_ONLY", script)
        self.assertIn(
            "const admissible = actions.filter(action => action.admissible === true);", script
        )
        self.assertIn("if (admissible.length && !data.recovery_request)", script)
        item_body = _js_function_body(script, "showTaskItem")
        self.assertIn("admissible.forEach(action => controls.append(actionButton(", item_body)
        self.assertNotIn("actions.forEach(action => controls", item_body)
        self.assertIn(
            "field(continuationList, 'New Task', continuation.new_task_id || '-')", item_body
        )
        self.assertIn("Open linked Task", item_body)
        self.assertNotIn("generic Retry", item_body)
        self.assertNotIn("retrySafe: true", item_body)
        recovery_body = _js_function_body(script, "confirmTaskRecovery")
        self.assertIn("Confirm ${label} for checkpoint ${checkpointVersion}?", recovery_body)
        self.assertIn(
            "/api/v1/tasks/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/recovery",
            recovery_body,
        )
        self.assertIn("actionId: action.action_id", recovery_body)
        self.assertIn("expectedCheckpointVersion: checkpointVersion", recovery_body)
        self.assertNotRegex(recovery_body, r"(?:actor|principal)\s*:")
        continuation_body = _js_function_body(script, "confirmRecoveryContinuation")
        self.assertIn("Confirm ${label} for checkpoint ${checkpointVersion}?", continuation_body)
        self.assertIn(
            "/recovery/continue",
            continuation_body,
        )
        self.assertIn("expectedCheckpointVersion: checkpointVersion", continuation_body)
        self.assertIn("analysis-only (DRY_RUN)", continuation_body)
        self.assertNotRegex(continuation_body, r"(?:actor|principal)\s*:")
        self.assertNotRegex(continuation_body, r"execute_authorized|authorityStatement")
        self.assertIn("mediaLibraryId", script)
        self.assertIn("Run Local setup check", script)
        self.assertIn("Activate checked Draft", script)
        self.assertIn("Credential readiness", script)
        self.assertIn("storageKinds", script)
        self.assertIn("guided.references", script)
        self.assertIn("referenceEvidence", script)
        self.assertIn("showing ${references.length}", script)
        self.assertIn("References (", script)
        self.assertIn("referencesTruncated", script)
        self.assertIn("configurationIdentityMatches", script)
        self.assertIn("Draft changed while loading", script)
        self.assertIn("Reload this revision", script)
        self.assertIn("Side effects: none", script)
        guard = script.index("if (guided && !configurationIdentityMatches")
        guided_render = script.index("renderGuidedObjectList(data, guided", guard)
        self.assertLess(guard, guided_render)
        mismatch = script[guard:guided_render]
        self.assertNotIn("Validate Draft", mismatch)
        self.assertNotIn("Save Draft", mismatch)
        self.assertNotIn("Activate", mismatch)
        self.assertIn("classificationPolicies", script)
        self.assertIn("recognitionRules", script)
        self.assertIn("metadataPolicies", script)
        self.assertIn("Save MetadataPolicy", script)
        self.assertIn("Effective MetadataPolicy", script)
        self.assertIn("Provider request / enrichment limits", script)
        self.assertIn("Run Recognition Strategy Test", script)
        self.assertIn("Task was not resumed", script)

    def test_manual_execution_discovery_and_unselected_state_are_reachable(self) -> None:
        script = APP_JS.decode()
        self.assertIn("renderManualExecutionDiscovery", script)
        self.assertIn("manualExecutionDiscovery", script)
        self.assertIn("Intent items not included in this Preview", script)
        self.assertIn("Intent/Preview items not executed", script)
        self.assertIn(
            "Unselected items have no TaskItem, Result, execution effect or Storage mutation",
            script,
        )
        self.assertIn("Reconcile interrupted execution", script)
        self.assertIn("Open durable execution", script)
        self.assertIn("showTaskItem(data.taskId, item.taskItemId)", script)

    def test_naming_policy_editor_and_exact_revision_preview_are_reachable(self) -> None:
        script = APP_JS.decode()
        show_revision = _js_function_body(script, "showConfigurationRevision")
        preview = _js_function_body(script, "renderNamingPreview")
        policy_mount = "renderGuidedObjectList(data, guided, 'namingPolicies', 'NamingPolicies');"
        preview_mount = "renderNamingPreview(data, guided);"

        self.assertIn(policy_mount, show_revision)
        self.assertIn(preview_mount, show_revision)
        guided_branch = show_revision.index("if (guided) {")
        guided_body = _js_braced_body(show_revision, show_revision.index("{", guided_branch))
        visible = show_revision.rindex("detail.hidden = false;")
        self.assertIn(policy_mount, guided_body)
        self.assertIn(preview_mount, guided_body)
        self.assertLess(guided_body.index(policy_mount), guided_body.index(preview_mount))
        self.assertLess(show_revision.index(preview_mount), visible)

        self.assertIn("detailContent.append(text('h3', 'Offline naming preview'));", preview)
        self.assertIn("detailContent.append(controls);", preview)
        self.assertIn("NamingPolicy preview policy", preview)
        self.assertIn("Naming preview sample JSON", preview)
        self.assertIn("Run offline naming preview", preview)
        self.assertIn("/naming-preview`,", preview)
        self.assertIn("expectedVersion: revision.version", preview)
        self.assertIn("expectedDigest: revision.digest", preview)
        self.assertIn("Rendered directory", preview)
        self.assertIn("Rendered filename", preview)
        self.assertIn("Sanitization", preview)
        self.assertIn("Missing-variable strategy", preview)
        self.assertIn("This preview is stale", preview)
        self.assertIn("Side effects", preview)

        object_list = _js_function_body(script, "renderGuidedObjectList")
        object_form = _js_function_body(script, "renderGuidedObjectForm")
        self.assertIn("Save NamingPolicy", object_form)
        self.assertIn("actionButton('Copy'", object_list)
        self.assertIn("References block deletion", object_list)

    def test_classification_policy_editor_and_preview_are_reachable(self) -> None:
        script = APP_JS.decode()
        show_revision = _js_function_body(script, "showConfigurationRevision")
        preview = _js_function_body(script, "renderClassificationPreview")
        policy_mount = (
            "renderGuidedObjectList(data, guided, 'classificationPolicies', "
            "'ClassificationPolicies');"
        )
        preview_mount = "renderClassificationPreview(data, guided);"
        guided_branch = show_revision.index("if (guided) {")
        guided_body = _js_braced_body(show_revision, show_revision.index("{", guided_branch))
        visible = show_revision.rindex("detail.hidden = false;")

        self.assertIn(policy_mount, guided_body)
        self.assertIn(preview_mount, guided_body)
        self.assertLess(guided_body.index(policy_mount), guided_body.index(preview_mount))
        self.assertLess(show_revision.index(preview_mount), visible)
        self.assertIn(
            "detailContent.append(text('h3', 'Offline classification preview'));",
            preview,
        )
        self.assertIn("detailContent.append(controls);", preview)
        self.assertIn("ClassificationPolicy preview policy", preview)
        self.assertIn("Classification preview sample JSON", preview)
        self.assertIn("Run offline classification preview", preview)
        self.assertIn("/classification-preview`,", preview)
        self.assertIn("expectedVersion: revision.version", preview)
        self.assertIn("expectedDigest: revision.digest", preview)
        self.assertIn("MediaLibrary resolved", preview)
        self.assertIn("Relative path", preview)
        self.assertIn("Matched rule name", preview)
        self.assertIn("Match evidence", preview)
        self.assertIn("This classification preview is stale", preview)

        object_list = _js_function_body(script, "renderGuidedObjectList")
        object_form = _js_function_body(script, "renderGuidedObjectForm")
        self.assertIn("Save ClassificationPolicy", object_form)
        self.assertIn("kind === 'classificationPolicies'", object_list)
        self.assertIn("actionButton('Copy'", object_list)
        self.assertIn("classification_policy", object_list)

    def test_organize_policy_editor_and_authority_explanation_are_reachable(self) -> None:
        script = APP_JS.decode()
        show_revision = _js_function_body(script, "showConfigurationRevision")
        authority = _js_function_body(script, "renderOrganizeAuthority")
        policy_mount = (
            "renderGuidedObjectList(data, guided, 'organizePolicies', 'OrganizePolicies');"
        )
        authority_mount = "renderOrganizeAuthority(data, guided);"
        guided_branch = show_revision.index("if (guided) {")
        guided_body = _js_braced_body(show_revision, show_revision.index("{", guided_branch))
        visible = show_revision.rindex("detail.hidden = false;")

        self.assertIn(policy_mount, guided_body)
        self.assertIn(authority_mount, guided_body)
        self.assertLess(guided_body.index(policy_mount), guided_body.index(authority_mount))
        self.assertLess(show_revision.index(authority_mount), visible)

        self.assertIn(
            "detailContent.append(text('h3', 'Offline organize authority explanation'));",
            authority,
        )
        self.assertIn("detailContent.append(controls);", authority)
        self.assertIn("Organize authority RecognitionType", authority)
        self.assertIn("Explain offline organize authority", authority)
        self.assertIn("/organize-authority`,", authority)
        self.assertIn("expectedVersion: revision.version", authority)
        self.assertIn("expectedDigest: revision.digest", authority)
        for label in (
            "'RecognitionTypePolicy'",
            "'OrganizePolicy'",
            "'Operation'",
            "'Conflict strategy'",
            "'Overwrite authorized'",
            "'Delete authorized'",
            "'Required Storage capabilities'",
            "'Fallback'",
            "'Destructive warnings'",
            "'Side effects'",
            "'Next action'",
        ):
            self.assertIn(label, authority)
        self.assertIn("This organize authority explanation is stale", authority)

        object_list = _js_function_body(script, "renderGuidedObjectList")
        object_form = _js_function_body(script, "renderGuidedObjectForm")
        self.assertIn("Save OrganizePolicy", object_form)
        self.assertIn("kind === 'organizePolicies'", object_list)
        self.assertIn("actionButton('Copy'", object_list)
        self.assertIn("organize_policy", object_list)
        self.assertIn("DESTRUCTIVE AUTHORITY", object_list)

    def test_destination_preview_is_reachable_and_attributed(self) -> None:
        script = APP_JS.decode()
        show_revision = _js_function_body(script, "showConfigurationRevision")
        preview = _js_function_body(script, "renderDestinationPreview")
        mount = "renderDestinationPreview(data, guided);"
        guided_start = show_revision.index("if (guided) {")
        guided_body = _js_braced_body(show_revision, show_revision.index("{", guided_start))
        visible = show_revision.rindex("detail.hidden = false;")

        self.assertIn(mount, guided_body)
        self.assertLess(show_revision.index(mount), visible)
        self.assertIn(
            "detailContent.append(text('h3', 'Offline composed destination preview'));",
            preview,
        )
        self.assertIn("detailContent.append(controls);", preview)
        self.assertIn("Destination preview RecognitionType", preview)
        self.assertIn("Destination preview sample JSON", preview)
        self.assertIn("Run offline destination preview", preview)
        self.assertIn("controls.append(recognitionType, sample, actionButton(", preview)
        self.assertIn("/destination-preview`,", preview)
        self.assertIn("expectedVersion: revision.version", preview)
        self.assertIn("expectedDigest: revision.digest", preview)
        self.assertIn("MediaLibrary contribution", preview)
        self.assertIn("ClassificationPolicy contribution", preview)
        self.assertIn("NamingPolicy directory contribution", preview)
        self.assertIn("NamingPolicy filename contribution", preview)
        self.assertIn("Composed Storage-relative destination", preview)
        self.assertIn("No valid destination was produced", preview)
        self.assertIn("configurationRevisionEditable(revision)", preview)

    def test_destination_precheck_is_reachable_read_only_and_actionable(self) -> None:
        script = APP_JS.decode()
        show_revision = _js_function_body(script, "showConfigurationRevision")
        precheck = _js_function_body(script, "renderDestinationPrecheck")
        activation = _js_function_body(script, "destinationPrecheckActivationRequirement")
        mount = "renderDestinationPrecheck(data, guided);"
        guided_start = show_revision.index("if (guided) {")
        guided_body = _js_braced_body(show_revision, show_revision.index("{", guided_start))
        visible = show_revision.rindex("detailContent.append(actions); detail.hidden = false;")

        self.assertIn(mount, guided_body)
        self.assertLess(show_revision.index(mount), visible)
        self.assertIn(
            "detailContent.append(text('h3', 'Read-only destination precheck'));",
            precheck,
        )
        for activation_line in (
            "nextAction = 'run the read-only destination precheck on this revision, then "
            "activate checked';",
            "nextAction = 'reload this revision and rerun the destination precheck on its "
            "current version and digest';",
            "Checked activation blocked: destination precheck failed (",
            "nextAction = 'change the configured operation or destination Storage, then "
            "rerun the precheck';",
        ):
            self.assertIn(activation_line, activation)
        self.assertIn(
            "Checked activation requirement: not applicable because this Draft has no "
            "MediaLibrary destination.",
            precheck,
        )
        self.assertIn(
            "Checked activation requirement: satisfied by current destination precheck evidence.",
            precheck,
        )
        self.assertIn("const activation = destinationPrecheckActivationRequirement", precheck)
        self.assertIn("else if (!activation.satisfied)", precheck)
        self.assertIn("const applicable = mediaLibraries.length > 0", activation)
        self.assertIn("controls.append(recognitionType, sample, actionButton(", precheck)
        self.assertIn("Destination precheck RecognitionType", precheck)
        self.assertIn("Destination precheck sample JSON", precheck)
        self.assertIn("Run read-only destination precheck", precheck)
        self.assertIn("detailContent.append(controls);", precheck)
        self.assertIn("configurationRevisionEditable(revision)", precheck)
        for label in (
            "Destination Storage",
            "MediaLibrary and Storage-relative root",
            "Deepest existing ancestor",
            "Directories that would be created",
            "Projected conflict outcome",
            "Proposed relative destination",
            "Required capabilities",
            "Declared destination capabilities",
            "Missing capabilities",
            "Read operations",
            "Authority granted",
        ):
            self.assertIn(label, precheck)
        self.assertIn("grants no overwrite, delete or execute authority", precheck)
        self.assertIn("no fallback to Copy or Move", precheck)
        self.assertIn("Destination is not ready", precheck)
        self.assertIn(
            "field(list, 'Destination path', boundedSetupText(result.destinationPath));",
            precheck,
        )

    def test_checked_activation_controls_share_destination_precheck_gate(self) -> None:
        script = APP_JS.decode()
        activation = _js_function_body(script, "destinationPrecheckActivationRequirement")
        checked = _js_function_body(script, "checkedActivationEvidenceIsCurrent")
        guided = _js_function_body(script, "renderRecognitionStrategyTest")
        show_revision = _js_function_body(script, "showConfigurationRevision")
        precheck = _js_function_body(script, "renderDestinationPrecheck")

        for predicate_line in (
            "const applicable = mediaLibraries.length > 0",
            "const current = destinationPrecheckIsCurrent(revision, evidence);",
            "const completed = Boolean(evidence && evidence.status === 'completed');",
            "evidence.result.verdict === 'capability_gap'",
            "const satisfied = !applicable || Boolean(current && completed && !capabilityGap);",
        ):
            self.assertIn(predicate_line, activation)
        self.assertIn(
            "destinationPrecheckActivationRequirement(revision, guided).satisfied", checked
        )
        self.assertIn("setupAndStrategyEvidenceIsCurrent(revision, guided)", checked)
        self.assertIn(
            "const activation = destinationPrecheckActivationRequirement(revision, guided);",
            precheck,
        )
        self.assertIn("else if (!activation.satisfied)", precheck)
        blocks = _js_function_body(script, "destinationPrecheckBlocksCheckedActivation")
        self.assertIn(
            "const requirement = destinationPrecheckActivationRequirement(revision, guided);",
            blocks,
        )
        self.assertIn(
            "if (!requirement.message || !setupAndStrategyEvidenceIsCurrent(revision, guided)) "
            "return null;",
            blocks,
        )
        self.assertIn(
            "const destination = destinationPrecheckBlocksCheckedActivation(revision, guided);",
            guided,
        )
        self.assertIn(
            "if (destination) detailContent.append(text('p', destination.message, "
            "destination.style));",
            guided,
        )
        self.assertIn(
            "const destination = destinationPrecheckBlocksCheckedActivation(data, guided);",
            show_revision,
        )
        self.assertIn(
            "checked activation is blocked by the destination precheck; ${destination.nextAction}.",
            show_revision,
        )
        self.assertIn(
            "requires current passed read-only Storage checks for every referenced "
            "enabled Storage and a current completed Recognition Strategy Test.",
            show_revision,
        )

    def test_destination_precheck_blocking_sentence_contract_is_body_scoped(self) -> None:
        script = APP_JS.decode()
        activation = _js_function_body(script, "destinationPrecheckActivationRequirement")
        precheck = _js_function_body(script, "renderDestinationPrecheck")

        missing_start = activation.index("if (applicable && !evidence) {")
        missing_branch = _js_braced_body(activation, activation.index("{", missing_start))
        self.assertIn(
            "nextAction = 'run the read-only destination precheck on this revision, then "
            "activate checked';",
            missing_branch,
        )
        self.assertIn("message = `Checked activation blocked: ${nextAction}.`;", missing_branch)

        stale_start = activation.index("if (applicable && !current) {")
        stale_branch = _js_braced_body(activation, activation.index("{", stale_start))
        self.assertIn(
            "nextAction = 'reload this revision and rerun the destination precheck on its "
            "current version and digest';",
            stale_branch,
        )
        self.assertIn("message = `Checked activation blocked: ${nextAction}.`;", stale_branch)

        failed_start = activation.index("if (applicable && !completed) {")
        failed_branch = _js_braced_body(activation, activation.index("{", failed_start))
        self.assertIn(
            "nextAction = boundedSetupText(evidence.nextAction,\n"
            "        'correct the destination configuration, then rerun the precheck');",
            failed_branch,
        )
        self.assertIn(
            "message = `Checked activation blocked: destination precheck failed "
            "(${boundedSetupText(evidence.failureCategory)}); ${nextAction}.`;",
            failed_branch,
        )
        self.assertIn("style = 'error';", failed_branch)

        gap_start = activation.index("if (applicable && capabilityGap) {")
        gap_branch = _js_braced_body(activation, activation.index("{", gap_start))
        self.assertIn(
            "nextAction = 'change the configured operation or destination Storage, then "
            "rerun the precheck';",
            gap_branch,
        )
        self.assertIn("message = `Checked activation blocked: ${nextAction}.`;", gap_branch)
        self.assertIn("style = 'error';", gap_branch)

        self.assertIn(
            "return {applicable, evidence, current, completed, capabilityGap, satisfied, "
            "nextAction, message, style};",
            activation,
        )
        self.assertIn(
            "else if (!activation.satisfied) detailContent.append(text('p', "
            "activation.message, activation.style));",
            precheck,
        )

    def test_destination_precheck_multi_sample_web_surface_is_falsifiable(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")

        self.assertIn(
            "const sampleCount = Number.isFinite(result.sampleCount) ? result.sampleCount : 1;",
            precheck,
        )
        self.assertIn("field(list, 'Sample count', String(sampleCount));", precheck)
        self.assertIn(
            "if (sampleCount > 1) {\n        const runList = document.createElement('dl');",
            precheck,
        )
        self.assertIn("if (Array.isArray(result.items)) {", precheck)
        self.assertIn("detailContent.append(text('h4', 'Per-sample destination rows'));", precheck)
        self.assertIn(
            "detailContent.append(table(['Sample', 'Destination', 'Projected outcome', "
            "'Failure category', 'Message', 'Next action'],",
            precheck,
        )
        self.assertIn("if (Array.isArray(result.collisions)) {", precheck)
        self.assertIn(
            "detailContent.append(text('h4', 'Cross-item destination collisions'));",
            precheck,
        )
        self.assertIn("detailContent.append(table(['Destination', 'Colliding samples'],", precheck)
        self.assertIn(
            "else detailContent.append(text('p', "
            "'No cross-item destination collision detected.'));",
            precheck,
        )
        self.assertIn(
            "sample.setAttribute('aria-label', 'Destination precheck sample JSON "
            "(one object, or an array of 1-8 samples)');",
            precheck,
        )
        self.assertIn(
            "controls.append(text('p', 'An array of samples detects cross-item "
            "destination collisions before activation.'));",
            precheck,
        )
        self.assertIn(
            "if (Array.isArray(parsed)) body.samples = parsed; else body.sample = parsed;",
            precheck,
        )
        self.assertIn("const body = {expectedVersion: revision.version,", precheck)

    def test_destination_precheck_run_level_summary_precedes_first_sample_block(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")

        multi_start = precheck.index("if (sampleCount > 1) {")
        multi_branch = _js_braced_body(precheck, precheck.index("{", multi_start))
        heading = "detailContent.append(text('h4', 'First sample destination'));"
        run_verdict = "field(runList, 'Run verdict (most severe sample)',"
        destination_path = "field(firstList, 'Destination path',"
        target_exists = "field(firstList, 'Target exists',"
        self.assertIn(heading, multi_branch)
        self.assertLess(multi_branch.index(run_verdict), multi_branch.index(heading))
        self.assertLess(
            multi_branch.index("detailContent.append(runList);"),
            multi_branch.index(heading),
        )
        self.assertLess(
            multi_branch.index(heading),
            multi_branch.index("detailContent.append(firstList);"),
        )
        self.assertLess(multi_branch.index(heading), multi_branch.index(destination_path))
        self.assertLess(multi_branch.index(destination_path), multi_branch.index(target_exists))
        self.assertIn("const firstList = document.createElement('dl');", multi_branch)
        self.assertIn("const runList = document.createElement('dl');", multi_branch)
        self.assertNotIn("field(list, 'Destination path',", multi_branch)
        self.assertNotIn("field(list, 'Target exists',", multi_branch)
        rows = precheck.index("detailContent.append(text('h4', 'Per-sample destination rows'));")
        self.assertLess(precheck.index(destination_path), rows)

    def test_destination_precheck_multi_sample_verdict_label_names_the_run(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")

        multi_start = precheck.index("if (sampleCount > 1) {")
        multi_branch = _js_braced_body(precheck, precheck.index("{", multi_start))
        single_branch = _js_braced_body(
            precheck, precheck.index("{", precheck.index("} else {", multi_start))
        )
        self.assertIn(
            "field(runList, 'Run verdict (most severe sample)', "
            "boundedSetupText(result.verdict || evidence.failureCategory));",
            multi_branch,
        )
        self.assertIn(
            "field(list, 'Verdict', boundedSetupText(result.verdict || evidence.failureCategory));",
            single_branch,
        )
        self.assertNotIn("Run verdict (most severe sample)", single_branch)

    def test_destination_precheck_absent_determinations_render_as_not_determined(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")

        multi_start = precheck.index("if (sampleCount > 1) {")
        multi_branch = _js_braced_body(precheck, precheck.index("{", multi_start))
        single_branch = _js_braced_body(
            precheck, precheck.index("{", precheck.index("} else {", multi_start))
        )
        root_field = (
            "field(runList, 'Destination root exists / directory', "
            "`${determinationText(result.destinationRootExists)} / "
            "${determinationText(result.destinationRootIsDirectory)}`);"
        )
        single_root_field = root_field.replace("runList", "list")
        self.assertIn(root_field, multi_branch)
        self.assertIn(
            "field(firstList, 'Target exists', determinationText(result.targetExists));",
            multi_branch,
        )
        self.assertIn(single_root_field, single_branch)
        self.assertIn(
            "field(list, 'Target exists', determinationText(result.targetExists));",
            single_branch,
        )
        self.assertEqual(precheck.count("determinationText(result.destinationRootExists)"), 2)
        self.assertEqual(precheck.count("determinationText(result.destinationRootIsDirectory)"), 2)
        self.assertEqual(precheck.count("determinationText(result.targetExists)"), 2)
        for expression in (
            "result.destinationRootExists === true ? 'YES' : 'NO'",
            "result.destinationRootIsDirectory === true ? 'YES' : 'NO'",
            "result.targetExists === true ? 'YES' : 'NO'",
        ):
            self.assertNotIn(expression, precheck)

    def test_determination_text_maps_true_false_and_undetermined_separately(self) -> None:
        script = APP_JS.decode()
        helper = _js_function_body(script, "determinationText")
        self.assertIn("if (value === true) return 'YES';", helper)
        self.assertIn("if (value === false) return 'NO';", helper)
        self.assertIn("return 'NOT DETERMINED';", helper)
        self.assertLess(
            script.index("function boundedSetupText(value, fallback = '-') {"),
            script.index("function determinationText(value) {"),
        )

    def test_destination_precheck_not_ready_gate_still_blocks_an_undetermined_root(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")
        self.assertIn(
            "if (evidence.status !== 'completed' || result.verdict === 'capability_gap' ||\n"
            "          !result.destinationRootExists || !result.destinationPath)",
            precheck,
        )
        self.assertIn(
            "detailContent.append(text('p',\n"
            "          'Destination is not ready. Follow the recovery action; no authority "
            "was granted.', 'error'));",
            precheck,
        )

    def test_destination_precheck_per_sample_rows_carry_each_sample_message(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")
        header = (
            "detailContent.append(table(['Sample', 'Destination', 'Projected outcome', "
            "'Failure category', 'Message', 'Next action'],"
        )
        self.assertIn(header, precheck)
        rows_start = precheck.index(header)
        rows_end = precheck.index("])));", rows_start) + len("])));")
        rows_expression = precheck[rows_start:rows_end]
        self.assertIn("boundedSetupText(item.message)", rows_expression)
        self.assertEqual(rows_expression.count("boundedSetupText(item.message)"), 1)
        self.assertLess(
            rows_expression.index("boundedSetupText(item.failureCategory)"),
            rows_expression.index("boundedSetupText(item.message)"),
        )
        self.assertNotIn("evidence.message", rows_expression)
        self.assertIn("detailContent.append(text('h4', 'Per-sample destination rows'));", precheck)
        self.assertIn("if (Array.isArray(result.items)) {", precheck)
        self.assertIn("field(runList, 'Message', boundedSetupText(evidence.message));", precheck)
        self.assertIn("field(list, 'Message', boundedSetupText(evidence.message));", precheck)

    def test_destination_precheck_per_sample_rows_render_each_sample_next_action(self) -> None:
        script = APP_JS.decode()
        precheck = _js_function_body(script, "renderDestinationPrecheck")
        header = (
            "detailContent.append(table(['Sample', 'Destination', 'Projected outcome', "
            "'Failure category', 'Message', 'Next action'],"
        )
        self.assertIn(header, precheck)
        rows_start = precheck.index(header)
        rows_end = precheck.index("])));", rows_start) + len("])));")
        rows_expression = precheck[rows_start:rows_end]
        self.assertEqual(rows_expression.count("boundedSetupText(item.nextAction)"), 1)
        self.assertLess(
            rows_expression.index("boundedSetupText(item.message)"),
            rows_expression.index("boundedSetupText(item.nextAction)"),
        )
        self.assertNotIn("evidence.nextAction", rows_expression)
        self.assertIn(
            "field(runList, 'Next action', boundedSetupText(evidence.nextAction));",
            precheck,
        )
        self.assertIn(
            "field(list, 'Next action', boundedSetupText(evidence.nextAction));",
            precheck,
        )

    def test_configuration_identity_mismatch_returns_before_all_normal_controls(self) -> None:
        script = APP_JS.decode()
        mismatch_start = script.index("function renderConfigurationIdentityMismatch")
        show_start = script.index("async function showConfigurationRevision", mismatch_start)
        table_start = script.index("function table(", show_start)
        mismatch_renderer = script[mismatch_start:show_start]
        show_revision = script[show_start:table_start]

        self.assertEqual(mismatch_renderer.count("actionButton("), 1)
        self.assertIn("actionButton('Reload this revision'", mismatch_renderer)
        self.assertIn("Raw revision", mismatch_renderer)
        self.assertIn("Guided revision", mismatch_renderer)
        self.assertIn("Side effects: none", mismatch_renderer)
        for forbidden in (
            "api(",
            "mutateGuidedObject",
            "activateConfigurationRevision",
            "Run Local setup check",
            "Save Draft",
            "Validate Draft",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, mismatch_renderer)

        guard = show_revision.index("if (guided && !configurationIdentityMatches")
        normal_detail = show_revision.index(
            "detailContent.append(text('h2', 'Configuration revision detail')", guard
        )
        guarded_branch = show_revision[guard:normal_detail]
        self.assertIn("renderConfigurationIdentityMismatch(revision, data, guided)", guarded_branch)
        self.assertIn("detail.hidden = false", guarded_branch)
        return_position = show_revision.index("return;", guard, normal_detail)
        self.assertLess(return_position, normal_detail)

        for normal_control in (
            "renderGuidedObjectList(data, guided",
            "renderLocalSetupActions(data, guided)",
            "actionButton('Validate Draft'",
            "document.createElement('textarea')",
            "actionButton('Save Draft'",
            "activateConfigurationRevision(data",
            "actionButton('Queue first DryRun Preview'",
        ):
            with self.subTest(normal_control=normal_control):
                self.assertLess(return_position, show_revision.index(normal_control, guard))

    def test_guided_object_form_retains_input_after_api_validation_failure(self) -> None:
        script = APP_JS.decode()
        mutation_start = script.index("async function mutateGuidedObject")
        list_start = script.index("function renderGuidedObjectList", mutation_start)
        mutation = script[mutation_start:list_start]
        api_call = mutation.index("await api(")
        success_hide = mutation.index("detail.hidden = true", api_call)
        success_reload = mutation.index("await renderConfiguration()", success_hide)
        self.assertLess(api_call, success_hide)
        self.assertLess(success_hide, success_reload)

        form_start = script.index("function renderGuidedObjectForm")
        actions_start = script.index("function renderLocalSetupActions", form_start)
        form = script[form_start:actions_start]
        save_start = form.index("actionButton('Save guided object'")
        back_start = form.index("actionButton('Back to revision'", save_start)
        save_handler = form[save_start:back_start]
        self.assertIn("guidedObjectPayload(kind, fields)", save_handler)
        self.assertIn("item && item.id", save_handler)
        self.assertIn("catch (error) { message(errorText(error), true); }", save_handler)
        for destructive_recovery in (
            "clear(detailContent)",
            "detail.hidden = true",
            "renderConfiguration()",
            "showConfigurationRevision(",
        ):
            with self.subTest(destructive_recovery=destructive_recovery):
                self.assertNotIn(destructive_recovery, save_handler)
        self.assertIn("Local Storage rootPath is a host-absolute directory", form)

    def test_validated_setup_failure_keeps_same_revision_editable_for_recovery(self) -> None:
        script = APP_JS.decode()
        helper_start = script.index("function configurationRevisionEditable")
        list_start = script.index("function renderGuidedObjectList", helper_start)
        helper = script[helper_start:list_start]
        self.assertIn("revision.status === 'draft' || revision.status === 'validated'", helper)
        self.assertGreaterEqual(script.count("configurationRevisionEditable("), 4)
        self.assertIn("Save guided object", script)
        self.assertIn("Save Draft", script)
        self.assertIn("Validate Draft", script)

    def test_local_setup_check_immediate_failure_is_actionable_without_retry_or_activation(
        self,
    ) -> None:
        script = APP_JS.decode()
        action_start = script.index("actionButton('Run Local setup check'")
        handler_end = script.index("function strategyEvidenceIsCurrent", action_start)
        handler = script[action_start:handler_end]
        self.assertIn("result.message", handler)
        self.assertIn("result.nextAction", handler)
        self.assertIn("result.sideEffects", handler)
        self.assertIn("result.retrySafe === true", handler)
        self.assertIn("Side effects:", handler)
        self.assertIn("Retry safe:", handler)
        self.assertNotIn("activateConfigurationRevision", handler)
        self.assertNotIn("setTimeout", handler)
        self.assertEqual(handler.count("local-setup-check"), 1)

    def test_persisted_local_setup_evidence_is_complete_bounded_and_read_only(self) -> None:
        script = APP_JS.decode()
        renderer_start = script.index("function renderLocalSetupEvidence")
        actions_start = script.index("function renderLocalSetupActions", renderer_start)
        renderer = script[renderer_start:actions_start]

        for label in (
            "Local setup check evidence",
            "Status: not run",
            "Evidence state",
            "Status",
            "Evidence revision ID",
            "Evidence version",
            "Evidence digest",
            "Current version",
            "Current digest",
            "Failure category",
            "Message",
            "Source root",
            "Destination root",
            "Completed operations",
            "Duration",
            "Side effects",
            "Retry safe",
            "Next action",
        ):
            with self.subTest(label=label):
                self.assertIn(label, renderer)
        self.assertIn("boundedSetupText", renderer)
        self.assertIn(".slice(0, 32)", renderer)
        self.assertIn("value.length <= 128", renderer)
        self.assertIn("Finish correcting this Draft, then Validate", renderer)
        self.assertIn("Run Local setup check again before checked activation", renderer)
        for forbidden in (
            "api(",
            "actionButton(",
            "activateConfigurationRevision",
            "setTimeout",
            "create_storages",
            "scan",
            "/api/v1/jobs",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, renderer)

    def test_setup_evidence_currentness_uses_exact_revision_identity(self) -> None:
        script = APP_JS.decode()
        helper_start = script.index("function setupEvidenceIsCurrent")
        renderer_start = script.index("function renderLocalSetupEvidence", helper_start)
        helper = script[helper_start:renderer_start]

        self.assertIn("evidence.stale === false", helper)
        self.assertIn("evidence.revisionId === revision.revisionId", helper)
        self.assertIn("evidence.revisionVersion === revision.version", helper)
        self.assertIn("evidence.revisionDigest === revision.digest", helper)

    def test_local_setup_selection_uses_enabled_local_backed_libraries(self) -> None:
        script = APP_JS.decode()
        helper_start = script.index("function localSetupSelection")
        actions_start = script.index("function renderLocalSetupActions", helper_start)
        helper = script[helper_start:actions_start]

        self.assertIn("new Set((objects.storages || [])", helper)
        self.assertIn(".filter(item => item.type === 'local').map(item => item.id)", helper)
        self.assertEqual(
            helper.count("item.enabled !== false && localBackendIds.has(item.storageId)"),
            2,
        )
        self.assertIn("objects.resourceLibraries || []", helper)
        self.assertIn("objects.mediaLibraries || []", helper)
        self.assertIn("return {resource: resources[0] || null, media: media[0] || null}", helper)
        self.assertNotIn("api(", helper)
        self.assertNotIn("actionButton(", helper)

    def test_reloaded_setup_state_has_explicit_safe_action_matrix(self) -> None:
        script = APP_JS.decode()
        actions_start = script.index("function renderLocalSetupActions")
        strategy_helper_start = script.index("function strategyEvidenceIsCurrent", actions_start)
        actions = script[actions_start:strategy_helper_start]

        selection = actions.index("const selection = localSetupSelection(guided)")
        draft_guard = actions.index("if (revision.status === 'draft')")
        validated_guard = actions.index("if (revision.status !== 'validated')")
        unavailable_guard = actions.index("if (!selection.resource || !selection.media)")
        run_action = actions.index("actionButton('Run Local setup check'")
        self.assertLess(selection, draft_guard)
        self.assertLess(draft_guard, validated_guard)
        self.assertLess(validated_guard, unavailable_guard)
        self.assertLess(unavailable_guard, run_action)
        self.assertIn("Validate this Draft before running Local setup check", actions)
        self.assertIn(
            "Configure and enable one Local-backed ResourceLibrary and MediaLibrary", actions
        )
        ineligible_path = actions[unavailable_guard:run_action]
        self.assertIn("return;", ineligible_path)
        self.assertNotIn("api(", ineligible_path)
        self.assertNotIn("actionButton(", ineligible_path)
        self.assertEqual(actions.count("actionButton('Run Local setup check'"), 1)
        self.assertEqual(actions.count("local-setup-check"), 1)
        self.assertIn("resourceLibraryId: selection.resource.id", actions)
        self.assertIn("mediaLibraryId: selection.media.id", actions)
        self.assertNotIn("guided.objects.resourceLibraries.filter", actions)
        self.assertNotIn("guided.objects.mediaLibraries.filter", actions)
        self.assertNotIn("activateConfigurationRevision", actions)

        setup_and_strategy = _js_function_body(script, "setupAndStrategyEvidenceIsCurrent")
        self.assertIn("referencedStorageChecksSatisfied(guided)", setup_and_strategy)
        self.assertIn("strategy.status === 'completed'", setup_and_strategy)
        self.assertIn("strategyEvidenceIsCurrent(revision, strategy)", setup_and_strategy)
        blocker_helper = _js_function_body(script, "firstStorageCheckBlocker")
        self.assertIn("storageCheckEvidenceFor(guided, storageId)", blocker_helper)
        self.assertIn("evidence.status !== 'passed'", blocker_helper)
        checked_helper = _js_function_body(script, "checkedActivationEvidenceIsCurrent")
        self.assertIn("setupAndStrategyEvidenceIsCurrent(revision, guided)", checked_helper)

        strategy_start = script.index("function renderRecognitionStrategyTest")
        strategy_end = script.index("async function activateConfigurationRevision", strategy_start)
        strategy = script[strategy_start:strategy_end]
        self.assertIn("checkedActivationEvidenceIsCurrent(revision, guided)", strategy)
        self.assertIn("Activate checked Draft", strategy)
        self.assertNotIn("setTimeout", actions)

        show_start = script.index("async function showConfigurationRevision")
        table_start = script.index("function table(", show_start)
        show_revision = script[show_start:table_start]
        evidence_render = show_revision.index("renderLocalSetupEvidence(data, guided)")
        action_render = show_revision.index("renderLocalSetupActions(data, guided)")
        self.assertLess(evidence_render, action_render)
        self.assertIn("checkedActivationEvidenceIsCurrent(data, guided)", show_revision)
        checked_branch = show_revision[show_revision.index("if (data.status === 'validated')") :]
        self.assertNotIn("setupEvidenceIsCurrent(data, guided.localSetupCheck)", checked_branch)
        self.assertIn("current passed read-only Storage checks", checked_branch)
        self.assertIn("current completed Recognition Strategy Test", checked_branch)

    def test_strategy_evidence_rows_are_bounded_explainable_and_read_only(self) -> None:
        script = APP_JS.decode()
        renderer_start = script.index("function renderStrategyEvidenceRows")
        metadata_start = script.index("function renderMetadataTestEvidence", renderer_start)
        strategy_start = script.index("function renderRecognitionStrategyTest", metadata_start)
        renderer = script[renderer_start:metadata_start]
        strategy_end = script.index("async function activateConfigurationRevision", strategy_start)
        strategy = script[strategy_start:strategy_end]

        self.assertIn("source.slice(0, 32)", renderer)
        self.assertIn("display limit 32", renderer)
        self.assertIn("Evidence display limit reached at 32 entries", renderer)
        for column in ("Rule ID", "RecognitionType", "Priority", "Score"):
            with self.subTest(column=column):
                self.assertIn(column, renderer)
        self.assertIn("boundedSetupText(item.ruleId)", renderer)
        self.assertIn("boundedSetupText(item.recognitionType)", renderer)
        self.assertIn("Number.isFinite(item.priority)", renderer)
        self.assertIn("Number.isFinite(item.score)", renderer)
        self.assertNotIn("api(", renderer)
        self.assertNotIn("actionButton(", renderer)

        self.assertIn(
            "renderStrategyEvidenceRows('Matched rules', recognition.matchedRules)", strategy
        )
        self.assertIn(
            "renderStrategyEvidenceRows('Alternatives', recognition.alternatives)", strategy
        )
        self.assertIn("field(list, 'Aggregate score'", strategy)
        self.assertIn("field(list, 'Confidence'", strategy)
        self.assertNotIn("Priority / score", strategy)
        self.assertIn("Recognition outcome", strategy)
        self.assertIn("Failure category", strategy)
        self.assertIn("Next action", strategy)
        self.assertIn("recognition.warnings.slice(0, 32)", strategy)
        self.assertIn("`Warning: ${boundedSetupText(warning)}`", strategy)
        self.assertIn("text('p'", strategy)
        self.assertNotIn("innerHTML", strategy)
        self.assertIn("result.result.recognition.status", strategy)
        self.assertIn("boundedSetupText(result.nextAction", strategy)
        self.assertIn("Strategy Test completed (", strategy)
        self.assertIn("Run Recognition Strategy Test (offline)", strategy)
        self.assertIn("Run live Metadata test", strategy)
        self.assertIn("liveMetadata", strategy)
        self.assertIn("renderMetadataTestEvidence", strategy)
        self.assertIn("Candidate explanation", APP_JS.decode())
        self.assertIn("Matched title", APP_JS.decode())
        self.assertIn("Candidates projected / total", APP_JS.decode())
        self.assertIn("Evidence truncated", APP_JS.decode())
        self.assertIn("highest-ranked evidence are preserved", APP_JS.decode())
        self.assertIn("Confirmed candidate rank", APP_JS.decode())
        self.assertIn("Confirmed Provider / ID", APP_JS.decode())
        self.assertIn("Identity match method", APP_JS.decode())
        self.assertIn("Confirm candidate ${index + 1}", APP_JS.decode())
        self.assertIn("expectedTestedAt: evidence.testedAt", strategy)
        self.assertIn("candidate-selection", strategy)
        self.assertIn("metadata-correction", strategy)
        self.assertIn("Run Metadata correction test", strategy)
        self.assertIn("Metadata correction mode", strategy)
        self.assertIn("Corrected query", strategy)
        self.assertIn("Direct Provider ID", strategy)
        self.assertIn("Corrected media type", strategy)
        self.assertIn("payload.providerId", strategy)
        self.assertIn("payload.query", strategy)
        self.assertIn("expectedTestedAt: evidence.testedAt", strategy)
        self.assertIn("Correction mode", APP_JS.decode())
        self.assertIn("Correction query / year", APP_JS.decode())
        self.assertIn("Correction Provider ID", APP_JS.decode())
        self.assertIn("const correctableMetadataOutcomes", strategy)
        self.assertIn("const correctionFailure", strategy)
        self.assertIn(
            "(correctableMetadataOutcomes.includes(metadataResult.status) || correctionFailure)",
            strategy,
        )
        self.assertIn("['provider_error', 'configuration_error']", strategy)
        self.assertNotIn(
            "correctableMetadataOutcomes.includes(metadataResult.status) ||\n"
            "          correctableMetadataOutcomes.includes(correctionSource)",
            strategy,
        )
        self.assertNotIn("providerSwitch", strategy)
        self.assertIn("metadataMatch.status === 'need_confirm'", strategy)
        self.assertIn("metadataMatch.status === 'ambiguous'", strategy)
        self.assertIn("revision.status === 'validated'", strategy)
        self.assertNotIn("Review its explanation before activation", strategy)


class AutomationPreviewWebTests(unittest.TestCase):
    def test_automation_outcome_summary_is_bounded_linked_and_read_only(self) -> None:
        script = APP_JS.decode("utf-8")
        detail = _js_function_body(script, "showAutomationDetail")
        render = _js_function_body(script, "renderAutomation")
        summary_start = detail.index(
            "detailContent.append(text('h3', 'Per-item outcome summary'));"
        )
        summary_end = detail.index("const occurrenceRows", summary_start)
        summary = detail[summary_start:summary_end]

        self.assertIn("'Per-item outcome summary'", summary)
        self.assertIn("cards(Object.entries(counts).map(([key, value]) => [key, value]))", summary)
        self.assertIn("bound.statement", summary)
        self.assertIn("Items needing attention", summary)
        self.assertIn("showTaskItem(attention[index].taskId, attention[index].itemId)", summary)
        self.assertIn("outcomeSummary.attentionLimit || 32", summary)
        self.assertIn("outcomeSummary.moreAttention === true", summary)
        self.assertIn("outcomeSummary.attentionTruncated === true", summary)
        self.assertIn("more items need review in the linked Task", summary)
        self.assertNotIn("confirmAutomationGrant", summary)
        self.assertNotIn("confirmAutomationGrantRevoke", summary)
        self.assertNotIn("method: 'POST'", summary)
        self.assertNotIn("method: 'PUT'", summary)
        self.assertNotIn("method: 'DELETE'", summary)

        task_item = _js_function_body(script, "showTaskItem")
        for field_name in (
            "Failure explanation",
            "Durable state",
            "Failure side effects",
            "Failure retry safe",
            "Failure next action",
        ):
            with self.subTest(field_name=field_name):
                self.assertIn(f"field(list, '{field_name}'", task_item)
        self.assertIn(
            "/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/occurrences?limit=10",
            detail,
        )
        self.assertIn("Opening or refreshing this view is read-only", detail)
        self.assertIn("index => showAutomationDetail(items[index], configuration)", render)

    def test_automation_preview_entry_confirm_render_and_read_only_load(self) -> None:
        script = APP_JS.decode("utf-8")
        detail = _js_function_body(script, "showAutomationDetail")
        self.assertIn("'Run Preview / DryRun'", detail)
        self.assertIn("confirmAutomationPreview(item)", detail)
        self.assertIn("previews?limit=10`", detail)
        self.assertIn("'No Preview has been run for this definition yet.'", detail)
        self.assertIn(
            "'Opening or refreshing this view is read-only. Preview runs only when "
            "you explicitly confirm it.'",
            detail,
        )
        self.assertNotIn("method: 'POST'", detail)
        self.assertNotIn("method: 'PUT'", detail)
        self.assertNotIn("method: 'DELETE'", detail)

        confirm = _js_function_body(script, "confirmAutomationPreview")
        self.assertIn("'Confirm Preview'", confirm)
        self.assertIn("It creates no Job, Task, grant, or configuration revision.", confirm)
        self.assertIn(
            "`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/preview`",
            confirm,
        )
        self.assertIn("method: 'POST'", confirm)

    def test_automation_grant_uses_shared_eligibility_projection(self) -> None:
        script = APP_JS.decode("utf-8")
        detail = _js_function_body(script, "showAutomationDetail")
        self.assertIn("/grant-state`", detail)
        self.assertIn("grantState.grantEligibility", detail)
        self.assertIn("grantEligibility.eligible === true", detail)
        self.assertIn("grantEligibility.previewId", detail)
        self.assertIn("Eligibility explanation", detail)
        self.assertIn("Eligibility next action", detail)
        self.assertNotIn(
            "latestPreview.current === true && latestPreview.status === 'previewed'", detail
        )
        self.assertNotIn("['Reviewed Preview'", detail)

        preview_view = _js_function_body(script, "showAutomationPreview")
        self.assertIn("'Automation Preview'", preview_view)
        self.assertIn("Stale evidence:", preview_view)
        self.assertIn("This is not execution authority.", preview_view)
        self.assertIn("'Definition fingerprint'", preview_view)
        self.assertIn("'Truncated by limit'", preview_view)
        self.assertIn("'Per-item evidence'", preview_view)
        self.assertIn("'Run a fresh Preview'", preview_view)
        self.assertIn("previews/${encodeURIComponent(previewId)}", preview_view)
        self.assertNotIn("method: 'POST'", preview_view)
        self.assertIn("data.itemsTruncated", preview_view)


class CurrentSourcePreviewWebTests(unittest.TestCase):
    def test_files_journey_previews_only_verified_membership_and_names_the_fallback(self) -> None:
        script = APP_JS.decode("utf-8")
        files = _js_function_body(script, "renderFiles")
        self.assertIn(
            "controls.append(manualScanLibraryControls(resourceLibraries, selectedStorage));", files
        )
        self.assertIn(
            "['Name', 'Type', 'Size', 'Modified', 'FileIndex', 'Manual Scan', 'Preview'], rows",
            files,
        )
        self.assertIn(
            "const previewPayload = item.isDirectory ? null : "
            "manualPreviewPayloadFromMembership(membership);",
            files,
        )
        self.assertIn(
            "actionButton('Preview file', () =>\n"
            "          confirmCurrentPreview(previewPayload, `Preview current FileIndex item "
            "${previewPayload.fileId}`))",
            files,
        )
        self.assertIn(
            "text('span', item.isDirectory ? '-' : "
            "'Preview unavailable until a verified current item exists')",
            files,
        )

    def test_file_index_journey_and_file_detail_offer_current_preview_actions(self) -> None:
        script = APP_JS.decode("utf-8")
        index = _js_function_body(script, "renderFileIndex")
        self.assertIn(
            "['ID', 'Path', 'Scan / discovery', 'Processing disposition',\n"
            "        'Current occurrence', 'Updated', 'Manual Scan', 'Preview'], rows",
            index,
        )
        self.assertIn("const previewPayload = manualPreviewPayloadFromFile(item);", index)
        self.assertIn(
            "actionButton('Preview', () =>\n"
            "          confirmCurrentPreview(previewPayload, `Preview current FileIndex item "
            "${fileId}`))",
            index,
        )
        self.assertIn("text('span', 'Preview unavailable until source is verified')", index)

        detail = _js_function_body(script, "showDetail")
        self.assertIn(
            "actionButton('Preview current source (DryRun)', () =>\n"
            "            confirmCurrentPreview(previewPayload, "
            "`Preview current FileIndex item ${id}`))",
            detail,
        )
        self.assertIn(
            "'Preview unavailable: select a verified ready current occurrence from FileIndex.'",
            detail,
        )

    def test_current_preview_payloads_admit_only_verified_bounded_identity_fields(self) -> None:
        script = APP_JS.decode("utf-8")
        from_file = _js_function_body(script, "manualPreviewPayloadFromFile")
        from_membership = _js_function_body(script, "manualPreviewPayloadFromMembership")

        self.assertIn("const scan = manualScanPayloadFromFile(item);", from_file)
        self.assertIn("if (!scan) return null;", from_file)
        self.assertIn(
            "return {scopeKind: 'file', resourceLibraryId: scan.resourceLibraryId,\n"
            "      occurrenceId: scan.occurrenceId, fingerprint: scan.fingerprint,\n"
            "      fileId: scan.fileId};",
            from_file,
        )
        self.assertIn(
            "item.scanStatus !== 'ready' || item.fingerprintState !== 'verified'",
            from_membership,
        )
        self.assertIn(
            "return {scopeKind: 'file', fileId: item.fileId,\n"
            "      resourceLibraryId: item.resourceLibraryId, occurrenceId: item.occurrenceId,\n"
            "      fingerprint: item.fingerprint};",
            from_membership,
        )
        # The Preview request body carries only current-identity fields: no Scan mode,
        # arbitrary path, operation, authority or Provider field may be admitted from the Web.
        self.assertNotIn("mode:", from_file)
        self.assertNotIn("mode:", from_membership)
        self.assertNotIn("path:", from_file)
        self.assertNotIn("path:", from_membership)
        self.assertNotIn("operation", from_file)
        self.assertNotIn("operation", from_membership)
        self.assertNotIn("authorize", from_file)
        self.assertNotIn("authorize", from_membership)

    def test_current_preview_confirmation_declares_persistence_and_zero_mutation(self) -> None:
        script = APP_JS.decode("utf-8")
        confirm = _js_function_body(script, "confirmCurrentPreview")
        self.assertIn(
            "message('Preview is unavailable until a verified current FileIndex occurrence "
            "is selected.', true);",
            confirm,
        )
        self.assertIn("text('h2', 'Confirm current-source Preview')", confirm)
        self.assertIn(
            "'no Task, review backlog, execution authority or Storage mutation is created.'",
            confirm,
        )
        self.assertIn(
            "const result = await api('/api/v1/manual-previews', {\n"
            "          method: 'POST', body: JSON.stringify(payload)\n"
            "        });",
            confirm,
        )
        self.assertIn("await showManualPreview(result.previewId);", confirm)
        self.assertIn(
            "message('Current-source Preview persisted. Storage was not changed and no "
            "execution authority was created.');",
            confirm,
        )
        self.assertIn("actionButton('Keep source unchanged', () => confirmation.remove())", confirm)
        self.assertNotIn("/manual-organize", confirm)

    def test_resource_library_journey_previews_the_bounded_library_scope(self) -> None:
        script = APP_JS.decode("utf-8")
        controls = _js_function_body(script, "manualScanLibraryControls")
        self.assertIn("actionButton(`Preview ${item.id}`, () =>", controls)
        self.assertIn(
            "confirmCurrentPreview({scopeKind: 'resource_library', resourceLibraryId: item.id},\n"
            "          `Preview ResourceLibrary ${item.id}`)));",
            controls,
        )

    def test_persisted_preview_detail_renders_scope_occurrence_and_mutation_state(self) -> None:
        script = APP_JS.decode("utf-8")
        detail = _js_function_body(script, "showManualPreview")
        self.assertIn(
            "await api('/api/v1/manual-previews/' + encodeURIComponent(previewId));", detail
        )
        self.assertIn("field(summary, 'Preview scope', scope.kind ?", detail)
        self.assertIn(
            "`${scope.kind}:${scope.id} (${scope.itemCount || 0} item(s))` : 'intent selection');",
            detail,
        )
        self.assertIn(
            "field(summary, 'Storage mutation', data.zeroMutation ? 'NONE' : 'INVALID');", detail
        )
        self.assertIn(
            "field(summary, 'Execution state', data.executionState || "
            "'not available in this Task');",
            detail,
        )
        self.assertIn("field(summary, 'Next action', data.nextAction || '-');", detail)
        self.assertIn(
            "item.itemId + ' - ' + item.status + ' (' +\n"
            "          (item.stage || 'analysis') + ')'",
            detail,
        )
        self.assertIn("'Current occurrence: ' + (source.occurrenceId || '-') +", detail)
        self.assertIn("'; state: ' + (source.occurrenceState || 'unverified')));", detail)
        self.assertIn("'RecognitionType: ' + (plan.recognitionType ||", detail)
        self.assertIn("'; NamingPolicy: ' + (policies.namingPolicyId || '-') +", detail)
        self.assertIn(
            "'Target: ' + (destination.storageId || '-') + ' / ' + (destination.path || '-') +",
            detail,
        )
        self.assertIn(
            "'; Required capabilities: ' + ((capabilities.required || []).join(', ') || 'none') +",
            detail,
        )
        self.assertIn("'; Recognition explanation: ' +", detail)
        self.assertIn("'Zero mutation: ' + (item.zeroMutation ? 'YES' : 'INVALID') +", detail)

    def test_persisted_preview_blockers_and_stale_items_expose_recovery_without_authority(
        self,
    ) -> None:
        script = APP_JS.decode("utf-8")
        detail = _js_function_body(script, "showManualPreview")
        self.assertIn(
            "if (item.error) section.append(text('p', 'Blocker/failure: ' + item.error, 'error'));",
            detail,
        )
        self.assertIn(
            "if (item.nextAction) section.append(text('p', 'Recovery: ' + item.nextAction, "
            "'warning'));",
            detail,
        )
        stale_start = detail.index(
            "if (item.status === 'stale' || data.status === 'stale' || data.current === false) {"
        )
        stale_branch = _js_braced_body(detail, detail.index("{", stale_start))
        self.assertIn(
            "section.append(actionButton('Request fresh Preview',\n"
            "            () => showManualIntent(data.intentId)));",
            stale_branch,
        )
        self.assertIn(
            "const executable = items.filter(item => item.status === 'previewed' && "
            "item.current &&\n        item.plan && item.plan.executionPlan && "
            "(!selectedIds.size || selectedIds.has(item.itemId)));",
            detail,
        )

    def test_manual_execution_blocker_section_and_resolution_are_served(self) -> None:
        script = APP_JS.decode("utf-8")
        execution_body = _js_function_body(script, "showManualExecution")
        self.assertIn("Review / conflict blockers", execution_body)
        self.assertIn(
            "${blocker.kind}: ${blocker.blocker_id || blocker.id} (${blocker.status})",
            execution_body,
        )
        self.assertIn("Open blocker resolution", execution_body)
        self.assertIn("showCheckpointBlocker(blocker.resolution_path)", execution_body)


if __name__ == "__main__":
    unittest.main()
