import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { TaskRefreshControl } from "./TaskRefreshControl";

it("accepts one manual refresh through a double click and stays busy until its reads settle", async () => {
  const user = userEvent.setup();
  let release!: () => void;
  const read = new Promise<void>((resolve) => {
    release = resolve;
  });
  const refresh = vi.fn(() => read);
  render(<TaskRefreshControl onRefresh={refresh} />);
  await user.dblClick(screen.getByRole("button", { name: "刷新" }));
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "刷新中…" })).toBeDisabled();
  release();
  expect(await screen.findByRole("button", { name: "刷新" })).toBeEnabled();
});
