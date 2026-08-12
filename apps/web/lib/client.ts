/**
 * Browser-side transport for the Junior Lawyer API.
 *
 * Requests go through the Next.js rewrite at /backend so they stay same-origin:
 * the session cookie is httpOnly and SameSite, and the API's SecurityMiddleware
 * rejects unsafe methods without a matching CSRF header. Login sets a readable
 * `jl_csrf` cookie for exactly this purpose, so unsafe requests echo it back.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/backend/api/v1";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)jl_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function withDefaults(init: RequestInit = {}): RequestInit {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken();
    if (token) headers.set("x-csrf-token", token);
  }
  // FormData sets its own multipart boundary; forcing JSON would corrupt it.
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  return { ...init, method, headers, credentials: "include" };
}

async function failure(response: Response): Promise<never> {
  let detail: unknown = null;
  const text = await response.text().catch(() => "");
  if (text) {
    try {
      detail = JSON.parse(text);
    } catch {
      detail = text;
    }
  }
  const record = detail as { detail?: unknown } | null;
  const raw = record && typeof record === "object" ? record.detail : detail;
  const message =
    typeof raw === "string" && raw
      ? raw
      : `Request failed with status ${response.status}`;
  throw new ApiError(response.status, detail, message);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, withDefaults(init));
  if (!response.ok) await failure(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** For endpoints that stream a generated PDF/DOCX rather than JSON. */
export async function apiFetchBlob(
  path: string,
  init: RequestInit = {},
): Promise<{ blob: Blob; filename: string | null; headers: Headers }> {
  const response = await fetch(`${API_BASE}${path}`, withDefaults(init));
  if (!response.ok) await failure(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  return {
    blob: await response.blob(),
    filename: match ? decodeURIComponent(match[1]) : null,
    headers: response.headers,
  };
}

export function jsonBody(payload: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(payload) };
}

/** Triggers a browser download for a blob returned by apiFetchBlob. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
