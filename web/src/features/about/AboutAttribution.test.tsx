import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import {
  AboutAttributionCard,
  TMDB_ATTRIBUTION_NOTICE,
} from "./AboutAttribution";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("AboutAttributionCard", () => {
  it("shows the product identity, approved local logo, exact notice and TMDB home link", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<AboutAttributionCard onClose={() => undefined} />);

    const region = screen.getByRole("region", { name: "数据来源与署名" });
    expect(region).toBeVisible();
    expect(screen.getByText("MediaFlow")).toBeVisible();
    expect(screen.getByText(/作品数据与图片来自 TMDB/)).toBeVisible();
    expect(screen.getByText(/不表示作品已入库/)).toBeVisible();
    expect(screen.getByText(TMDB_ATTRIBUTION_NOTICE)).toBeVisible();
    const logo = screen.getByRole("img", { name: "TMDB" });
    expect(logo).toHaveAttribute(
      "src",
      expect.stringContaining("tmdb-logo.svg"),
    );
    expect(logo).toHaveAttribute("alt", "TMDB");
    const link = screen.getByRole("link", { name: /访问 TMDB 首页/ });
    expect(link).toHaveAttribute("href", "https://www.themoviedb.org");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("closes through the shared card exit without reading anything", () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const onClose = vi.fn();
    render(<AboutAttributionCard onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: "关闭关于与鸣谢" }));
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
