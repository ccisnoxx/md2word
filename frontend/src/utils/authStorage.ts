// frontend/src/utils/authStorage.ts: Store the JWT used by API requests.
const TOKEN_KEY = "md2word.frontend.access_token";

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}
