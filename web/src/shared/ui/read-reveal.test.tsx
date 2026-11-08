import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { useReadReveal } from "./read-reveal";

function Probe({
  pending,
  label,
}: {
  readonly pending: boolean;
  readonly label: string;
}) {
  const revealed = useReadReveal(pending);
  return revealed ? (
    <p role="status">{label}</p>
  ) : (
    <p data-testid="idle">idle</p>
  );
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("useReadReveal", () => {
  it("never reveals the waiting feedback when the read settles first", () => {
    vi.useFakeTimers();
    const view = render(<Probe pending label="slow read" />);

    // A read that finishes inside the window is over before the gate opens.
    act(() => {
      vi.advanceTimersByTime(100);
    });
    view.rerender(<Probe pending={false} label="slow read" />);
    // Even far past the original deadline the settled read shows no waiting
    // feedback: the gate re-arms only for a new pending state.
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("reveals one stable busy state only after the read is genuinely slow", () => {
    vi.useFakeTimers();
    render(<Probe pending label="slow read" />);
    expect(screen.queryByRole("status")).toBeNull();

    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("status")).toHaveTextContent("slow read");

    // It stays visible while the read is still outstanding: one stable state,
    // not a repeating flash.
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("status")).toHaveTextContent("slow read");
  });

  it("hides a settled read immediately and re-arms for the next one", () => {
    vi.useFakeTimers();
    const view = render(<Probe pending label="read one" />);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("status")).toHaveTextContent("read one");

    view.rerender(<Probe pending={false} label="read one" />);
    expect(screen.queryByRole("status")).toBeNull();

    // The second read starts over: fast again it stays hidden, slow again it
    // reappears as one stable state.
    view.rerender(<Probe pending label="read two" />);
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(screen.queryByRole("status")).toBeNull();
    view.rerender(<Probe pending={false} label="read two" />);
    view.rerender(<Probe pending label="read two" />);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("status")).toHaveTextContent("read two");
  });
});
