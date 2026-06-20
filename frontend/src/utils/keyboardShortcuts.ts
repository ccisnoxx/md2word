// File: frontend/src/utils/keyboardShortcuts.ts
// Purpose: Shared keyboard shortcut guards and command-palette trigger helpers.

export type ShortcutHint = {
  keys: string[];
  label: string;
};

export function isEditableShortcutTarget(target: EventTarget | null): boolean {
  if (typeof HTMLElement === "undefined") {
    return false;
  }
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select" || Boolean(target.closest("[contenteditable='true']"));
}

export function isCommandPaletteShortcut(event: KeyboardEvent): boolean {
  return (event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k";
}

