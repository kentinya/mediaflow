import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { normalizeAttachmentResults } from "../../entities/operations/task";
import { AttachmentResults } from "./AttachmentResults";

describe("independent attachment outcomes", () => {
  it("shows primary completion and exact policy-derived conflict guidance without replay controls", () => {
    const results = normalizeAttachmentResults([
      {
        type: "subtitle",
        language: "en",
        operation: "COPY",
        status: "not_executed",
        reason: "attachment_collision",
        source_storage_id: "source",
        source_path: "Incoming/One.en.srt",
        destination_storage_id: "target",
        destination_path: "Movies/One.en.srt",
        effect_certainty: "none",
        completed_operations: [],
        next_action:
          "有冲突：One.en.srt，请修正后再进行‘复制’操作（仅该附件，不重放主文件）。",
      },
    ]);
    render(<AttachmentResults primaryCompleted results={results} />);
    expect(screen.getByText("主文件已完成；附件有警告")).toBeVisible();
    expect(
      screen.getByText(
        /source:Incoming\/One.en.srt → target:Movies\/One.en.srt/,
      ),
    ).toBeVisible();
    expect(screen.getByText(/请修正后再进行‘复制’操作/)).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("preserves investigation-only guidance for unknown effects", () => {
    const results = normalizeAttachmentResults([
      {
        type: "nfo",
        language: null,
        operation: "MOVE",
        status: "failed",
        reason: "verification_failed",
        source_storage_id: "source",
        source_path: "One.nfo",
        destination_storage_id: "target",
        destination_path: "Movies/One.nfo",
        effect_certainty: "attempted_unverified",
        completed_operations: ["COPY"],
        next_action:
          "效果尚未确认，请核查附件来源、目标及持久步骤；不要重放主文件或附件。",
      },
    ]);
    render(<AttachmentResults primaryCompleted results={results} />);
    expect(screen.getByText(/不要重放主文件或附件/)).toBeVisible();
    expect(screen.getByText(/已完成步骤：COPY/)).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("rejects malformed and unbounded outcomes", () => {
    expect(() => normalizeAttachmentResults([{}])).toThrow();
    expect(() => normalizeAttachmentResults(Array(65).fill({}))).toThrow();
  });
});
