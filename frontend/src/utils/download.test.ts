import { afterEach, describe, expect, it, vi } from "vitest";

import { openDownloadLink } from "@/utils/download";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("openDownloadLink", () => {
  it("新窗口打开成功时返回 true 并断开 opener", () => {
    const opened = { opener: {} as unknown };
    const open = vi.fn(() => opened);
    vi.stubGlobal("window", { open });
    expect(openDownloadLink("https://files.example/doc.docx")).toBe(true);
    expect(open).toHaveBeenCalledExactlyOnceWith("https://files.example/doc.docx", "_blank");
    expect(opened.opener).toBeNull();
  });

  it("新窗口被浏览器拦截时返回 false", () => {
    vi.stubGlobal("window", { open: vi.fn(() => null) });
    expect(openDownloadLink("https://files.example/doc.docx")).toBe(false);
  });
});
