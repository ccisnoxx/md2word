// File: frontend/tests/smoke/support/accessibility.ts
// Purpose: Shared viewport, overflow, skip-link, and overlay-fit assertions for smoke gates.
import { expect, type Locator, type Page } from "@playwright/test";

export const WORKBENCH_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "laptop", width: 1024, height: 768 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 375, height: 812 },
] as const;

export async function expectNoPageHorizontalOverflow(page: Page): Promise<void> {
  const sizes = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    document: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(sizes.body, `body width ${sizes.body} exceeds viewport ${sizes.viewport}`).toBeLessThanOrEqual(sizes.viewport + 1);
  expect(sizes.document, `document width ${sizes.document} exceeds viewport ${sizes.viewport}`).toBeLessThanOrEqual(
    sizes.viewport + 1,
  );
}

export async function expectElementContentFitsViewportWidth(page: Page, locator: Locator): Promise<void> {
  const viewport = page.viewportSize();
  expect(viewport, "viewport should be available").not.toBeNull();
  if (!viewport) {
    return;
  }
  const metrics = await locator.evaluate((node) => {
    const element = node as HTMLElement;
    return {
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    };
  });
  expect(metrics.clientWidth, "element should fit the viewport width").toBeLessThanOrEqual(viewport.width + 1);
  expect(metrics.scrollWidth, "element content should not overflow horizontally").toBeLessThanOrEqual(metrics.clientWidth + 1);
}

export async function activateSkipLink(
  page: Page,
  options: { linkName?: string; targetId?: string } = {},
): Promise<void> {
  const linkName = options.linkName || "跳到主内容";
  const targetId = options.targetId || "app-main-content";
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: linkName })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe(targetId);
}
