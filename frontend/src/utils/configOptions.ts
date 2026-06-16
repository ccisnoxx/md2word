// File: frontend/src/utils/configOptions.ts
// Purpose: Keep document job config option selection on canonical resource/version values.
import type { DocumentJobConfigVersionOption } from "@/api/types";

export function configOptionKey(option: DocumentJobConfigVersionOption): string {
  return `${option.resource_id}@${option.version}`;
}

export function findConfigOption(
  options: DocumentJobConfigVersionOption[],
  selectedValue: string,
): DocumentJobConfigVersionOption | null {
  const value = selectedValue.trim();
  if (!value) {
    return null;
  }
  return (
    options.find((option) => configOptionKey(option) === value)
    || options.find((option) => option.label === value)
    || null
  );
}

export function configVersionId(option: DocumentJobConfigVersionOption): string {
  return configOptionKey(option);
}
