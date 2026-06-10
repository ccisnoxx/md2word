// File: frontend/src/utils/download.ts
// Purpose: Share browser download-link handling across document job pages.

export type DownloadLinkNotice = {
  label: string;
  url: string;
  expiresAt: string;
  fileName?: string | null;
};

export function openDownloadLink(url: string): boolean {
  const opened = window.open(url, "_blank", "noopener");
  return opened !== null;
}

export async function copyDownloadLink(url: string): Promise<boolean> {
  if (!navigator.clipboard) {
    return false;
  }
  await navigator.clipboard.writeText(url);
  return true;
}
