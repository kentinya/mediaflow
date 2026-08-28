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
        self.assertNotIn("overwrite", script.lower())
        self.assertIn("Queue DryRun job", script)
        self.assertIn("'/api/v1/jobs', {method: 'POST'", script)
        self.assertNotIn("/api/v1/tasks/${encodeURIComponent(id)}/resume", script)
        self.assertNotIn("actor", script.lower())
        self.assertIn("mediaLibraryId", script)
        self.assertIn("Run Local setup check", script)
        self.assertIn("Activate checked Draft", script)
        self.assertIn("Remote/read-only here", script)
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

        checked_helper_start = script.index("function checkedActivationEvidenceIsCurrent")
        row_renderer_start = script.index(
            "function renderStrategyEvidenceRows", checked_helper_start
        )
        checked_helper = script[checked_helper_start:row_renderer_start]
        self.assertIn("local.status === 'passed'", checked_helper)
        self.assertIn("setupEvidenceIsCurrent(revision, local)", checked_helper)
        self.assertIn("strategy.status === 'completed'", checked_helper)
        self.assertIn("strategyEvidenceIsCurrent(revision, strategy)", checked_helper)

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
        self.assertIn("current passed Local setup check", checked_branch)
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


if __name__ == "__main__":
    unittest.main()
