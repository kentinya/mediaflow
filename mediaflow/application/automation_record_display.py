"""Concise records-only read projection; never grants recovery or execution."""

from mediaflow.application.operations_lifecycle import bounded_failure_document

# Closed explanations, not adapter/exception text or instructions from storage.
_REASONS = {
    "scope_root_unavailable": ("来源目录无法读取", "检查来源目录、存储连接和读取权限"),
    "scope_root_not_directory": ("来源范围不是目录", "检查自动化来源范围设置"),
    "scope_root_invalid": ("来源范围设置无效", "检查自动化来源范围设置"),
    "scope_outside_resource_library": ("来源范围超出资源库", "检查自动化来源范围设置"),
    "definition_missing": ("本次运行的自动化配置不可用", "检查自动化定义"),
    "definition_invalid": ("本次运行的自动化配置无效", "检查自动化定义设置"),
    "definition_disabled": ("本次运行对应的自动化已停用", "检查自动化启用状态"),
    "resource_library_missing": ("本次运行的来源资源库不可用", "检查来源资源库设置"),
    "resource_library_disabled": ("来源资源库已停用", "检查来源资源库启用状态"),
    "snapshot_missing": ("本次运行使用的配置无法读取", "检查配置是否可用"),
    "automation_execution_authority_unavailable": ("本次运行缺少执行权限", "检查执行权限"),
    "scope_root_missing": ("来源目录不存在", "检查来源目录和自动化范围设置"),
    "source_missing": ("来源文件不存在", "检查对应的来源文件"),
    "source_changed": ("来源文件已改变", "核对对应的来源文件"),
    "source_unverified": ("无法核对来源文件", "核对对应的来源文件"),
    "source_already_organizing": ("文件已属于另一个未结束的整理任务", "检查该文件已有的整理任务"),
    "unstable_source": ("文件仍在写入或尚未稳定", "等待文件写入完成，并检查稳定性设置"),
    "storage_failure": ("文件存储操作未完成", "检查来源、目标文件和存储连接及权限"),
    "provider_failure": ("媒体信息查询未完成", "检查媒体信息服务的连接和设置"),
    "recognition_failure": ("未确定文件的识别类型", "检查对应文件和识别规则"),
    "metadata_failure": ("未确定媒体信息", "检查对应文件的媒体信息"),
    "naming_failure": ("未生成可用的文件名", "检查文件命名设置"),
    "classification_failure": ("未确定可用的整理目标", "检查目标媒体库和分类设置"),
    "invalid_destination": ("整理目标不可用", "检查目标媒体库和路径设置"),
    "destination_collision": ("目标已有同名文件", "检查目标文件和同名文件处理设置"),
    "attachment_collision": ("目标已有同名附件", "检查目标附件和同名文件处理设置"),
    "unsupported_capability": ("存储不支持所选操作", "检查存储能力和整理操作设置"),
    "denied_capability": ("存储不允许所选操作", "检查存储权限和整理操作设置"),
    "unattended_authority": ("执行权限已失效，操作已停止", "检查自动化启用状态和执行权限"),
    "uncertain_effect": ("有操作的效果尚未确认", "先核对来源和目标文件，勿重复执行"),
    "partial_effect": ("部分文件操作未完成", "核对已完成的操作及来源、目标文件"),
}


def automation_record_display(overview, failure_evidence: dict | None) -> dict[str, object]:
    """Use the same SQL outcome consumed by server filtering, not live handling."""
    evidence = overview.automation_record_evidence or {}
    status = evidence.get("record_outcome", "unknown")
    success = int(evidence.get("success_count") or 0)
    no_work = status == "completed" and evidence.get("item_count") in {None, 0}
    result = {
        "status": status,
        "noWork": no_work,
        "successItems": success,
        "statement": "本次结果无法核对",
        "failureReason": None,
        "nextStep": "刷新记录以核对结果；核对前勿重复执行",
    }
    if status == "completed":
        result.update(
            statement="本次成功：无工作完成" if no_work else f"本次成功，已整理 {success} 个文件",
            nextStep="本次无需修复；不代表来源文件已全部处理",
        )
    elif status in {"pending", "running", "paused", "waiting"}:
        result.update(
            statement={
                "pending": "本次正在等待执行",
                "running": "本次正在执行",
                "paused": "本次已暂停，尚未结束",
                "waiting": "本次正在等待，尚未结束",
            }[status],
            nextStep="等待本次运行结束后刷新查看结果"
            if status != "paused"
            else "本次仍处于暂停状态，结束后再查看结果",
        )
    elif status == "failed":
        reasons, steps = [], []
        cancelled = evidence.get("original_status") == "cancelled"
        if cancelled:
            reasons.append("本次运行已取消")
            steps.append("本次已取消；已完成的操作保留")
        skipped = int(evidence.get("skipped_count") or 0)
        if skipped:
            reasons.append(f"按策略跳过或忽略了 {skipped} 个文件")
            steps.append("检查对应文件和跳过、同名文件处理设置")
        if evidence.get("cancelled_count") and not cancelled:
            reasons.append("部分文件处理已取消")
            steps.append("检查已取消的文件；已完成的操作保留")
        if evidence.get("attachment_failed_count"):
            reasons.append("关联附件未全部完成")
            steps.append("检查关联附件的来源、目标和处理设置")
        # Failure samples are bounded, but their categories are backend-decoded,
        # never raw exception text. Full-population counts come from SQL.
        categories = []
        if not overview.task_id and overview.attention_failure_category:
            categories.append(overview.attention_failure_category)
        for item in (failure_evidence or {}).get("items", []):
            error = item.get("error")
            document = bounded_failure_document(error) if error else None
            if document:
                categories.append(document.get("category"))
        for item in (failure_evidence or {}).get("items", []):
            for reason in item.get("attachmentReasons", []):
                category = {
                    "attachment_collision": "attachment_collision",
                    "source_missing": "source_missing",
                    "authority_refused": "unattended_authority",
                    "execution_stopped": "partial_effect",
                }.get(reason)
                if category:
                    categories.append(category)
        for category in dict.fromkeys(categories):
            if category in _REASONS:
                reason, step = _REASONS[category]
                reasons.append(reason)
                steps.append(step)
        uncertain = bool(evidence.get("uncertain_count")) or bool(
            (failure_evidence or {}).get("effects", {}).get("uncertain")
        )
        partial = bool(evidence.get("partial_effect_count")) or bool(
            (failure_evidence or {}).get("effects", {}).get("partial")
        )
        if uncertain:
            reasons.append("有操作的效果尚未确认")
            steps = ["先核对来源和目标文件，勿重复执行"]
        elif partial:
            reasons.append("部分操作已完成，其余未完成")
            steps.append("核对已完成的操作，勿重复执行已完成部分")
        if not reasons:
            reasons.append("本次未全部完成，具体原因当前不可读")
            steps.append("刷新核对失败原因，并检查对应文件")
        elif evidence.get("failed_count") and not any(c in _REASONS for c in categories):
            reasons.append("部分文件的具体失败原因当前不可读")
        if (failure_evidence or {}).get("truncated"):
            reasons.append("失败原因未全部展示")
        if evidence.get("unreadable_count"):
            reasons.append("部分文件结果不可核对")
        effects = f"；已确认整理 {success} 个文件，已完成的操作保留" if success else ""
        result.update(
            statement="本次失败，未全部完成" + effects,
            failureReason="；".join(dict.fromkeys(reasons)),
            nextStep="；".join(dict.fromkeys(steps)) or "检查对应文件及具体失败原因",
        )
    return result
