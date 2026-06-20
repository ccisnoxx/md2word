import { describe, expect, it } from "vitest";

import { isCommandPaletteShortcut, isEditableShortcutTarget } from "@/utils/keyboardShortcuts";

describe("keyboard shortcut helpers", () => {
  it("detects Cmd/Ctrl+K without treating other modified keys as command-palette triggers", () => {
    expect(isCommandPaletteShortcut({ key: "k", metaKey: true, ctrlKey: false, altKey: false } as KeyboardEvent)).toBe(true);
    expect(isCommandPaletteShortcut({ key: "K", metaKey: false, ctrlKey: true, altKey: false } as KeyboardEvent)).toBe(true);
    expect(isCommandPaletteShortcut({ key: "k", metaKey: false, ctrlKey: false, altKey: false } as KeyboardEvent)).toBe(false);
    expect(isCommandPaletteShortcut({ key: "k", metaKey: true, ctrlKey: false, altKey: true } as KeyboardEvent)).toBe(false);
  });

  it("is safe when editable target checks run outside a browser DOM", () => {
    expect(isEditableShortcutTarget(null)).toBe(false);
  });
});

