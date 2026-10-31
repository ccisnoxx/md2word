// 文件：frontend/src/utils/download.ts
// 用途：共享任务页面的下载链接处理和同次签发提示。

export type DownloadLinkNotice = {
  label: string;
  url: string;
  expiresAt: string;
  fileName?: string | null;
  notice?: string;
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
