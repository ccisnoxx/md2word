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
  // 带 noopener 时 window.open 按规范总是返回 null，无法判断是否被拦截；改为打开后手动断开 opener。
  const opened = window.open(url, "_blank");
  if (opened === null) {
    return false;
  }
  opened.opener = null;
  return true;
}

export async function copyDownloadLink(url: string): Promise<boolean> {
  if (!navigator.clipboard) {
    return false;
  }
  await navigator.clipboard.writeText(url);
  return true;
}
