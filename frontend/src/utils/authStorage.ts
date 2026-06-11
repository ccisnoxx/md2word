// frontend/src/utils/authStorage.ts: Store the JWT used by API requests.
const TOKEN_KEY = "md2word.frontend.access_token";
let memoryToken: string | null = null;

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function getStoredToken(): string | null {
  return browserStorage()?.getItem(TOKEN_KEY) ?? memoryToken;
}

export function setStoredToken(token: string): void {
  memoryToken = token;
  browserStorage()?.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  memoryToken = null;
  browserStorage()?.removeItem(TOKEN_KEY);
}
