const fallbackBaseUrl = '/api';
export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || fallbackBaseUrl).replace(/\/$/, '');

const accessTokenKey = 'equi.access-token';
const refreshTokenKey = 'equi.refresh-token';

type ApiFieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly code?: string,
    public readonly fieldErrors: ApiFieldErrors = {},
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(accessTokenKey);
}

export function resolveFileUrl(fileUrl: string): string {
  if (/^https?:\/\//i.test(fileUrl)) return fileUrl;
  const base = new URL(apiBaseUrl, window.location.origin);
  const basePath = base.pathname.replace(/\/+$/, '');
  const url = basePath && fileUrl.startsWith(`${basePath}/`)
    ? new URL(fileUrl, base.origin)
    : new URL(fileUrl.replace(/^\/+/, ''), `${base.origin}${basePath}/`);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new ApiError('Liên kết tài liệu phải dùng HTTP hoặc HTTPS.');
  }
  return url.href;
}

export function saveSession(access: string, refresh: string): void {
  localStorage.removeItem('equi_access_token');
  localStorage.removeItem('equi_refresh_token');
  localStorage.setItem(accessTokenKey, access);
  localStorage.setItem(refreshTokenKey, refresh);
}

export function clearSession(): void {
  localStorage.removeItem(accessTokenKey);
  localStorage.removeItem(refreshTokenKey);
  localStorage.removeItem('equi_access_token');
  localStorage.removeItem('equi_refresh_token');
}

function errorMessage(value: unknown, status: number): {
  message: string;
  code?: string;
  fieldErrors: ApiFieldErrors;
} {
  if (value && typeof value === 'object') {
    const body = value as Record<string, unknown>;
    const code = typeof body.code === 'string' ? body.code : undefined;
    const fieldErrors = Object.fromEntries(
      Object.entries(body)
        .filter(([field]) => field !== 'detail' && field !== 'code' && field !== 'non_field_errors')
        .flatMap(([field, errors]) => {
          const values = Array.isArray(errors) ? errors : [errors];
          const messages = values.filter((item): item is string => typeof item === 'string');
          return messages.length ? [[field, messages]] : [];
        }),
    );
    if (typeof body.detail === 'string') return { message: body.detail, code, fieldErrors };
    const messages = Object.entries(body)
      .flatMap(([field, errors]) => {
        const values = Array.isArray(errors) ? errors : [errors];
        return values.filter((item): item is string => typeof item === 'string')
          .map((item) => field === 'detail' ? item : `${field}: ${item}`);
      });
    if (messages.length) return { message: messages.join(' '), code, fieldErrors };
  }
  // An HTML/plain-text server failure may contain a debug traceback or proxy internals.
  if (status >= 500 || (typeof value === 'string' && /<!doctype|<html|Traceback|ProgrammingError|OperationalError/i.test(value))) {
    return { message: 'Máy chủ đang gặp lỗi. Vui lòng thử lại hoặc liên hệ quản lý hệ thống.', fieldErrors: {} };
  }
  if (typeof value === 'string' && value) return { message: value, fieldErrors: {} };
  return { message: `Yêu cầu thất bại (HTTP ${status}).`, fieldErrors: {} };
}

async function send(path: string, init: RequestInit, authenticated: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body instanceof FormData) headers.delete('Content-Type');
  else if (init.body !== undefined) headers.set('Content-Type', 'application/json');
  const token = authenticated ? getAccessToken() : null;
  if (token) headers.set('Authorization', `Bearer ${token}`);

  try {
    return await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : 'Không thể kết nối API.');
  }
}

let refreshPromise: Promise<string | null> | undefined;

async function performRefresh(): Promise<string | null> {
  const refresh = localStorage.getItem(refreshTokenKey);
  if (!refresh) return null;

  const response = await send('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh }),
  }, false);
  if (!response.ok) {
    if (response.status === 400 || response.status === 401 || response.status === 403) return null;
    throw new ApiError('Máy chủ chưa thể gia hạn phiên. Vui lòng thử lại.', response.status);
  }
  const body = await response.json() as { access?: unknown };
  if (typeof body.access !== 'string' || !body.access) return null;
  // A response from an old session must not resurrect it after logout or another login.
  if (localStorage.getItem(refreshTokenKey) !== refresh) return null;
  localStorage.setItem(accessTokenKey, body.access);
  return body.access;
}

function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => { refreshPromise = undefined; });
  }
  return refreshPromise;
}

function expireSession(): void {
  clearSession();
  window.dispatchEvent(new Event('equi:session-expired'));
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
  parseResponse: (response: Response) => Promise<T> = (response) => response.json() as Promise<T>,
): Promise<T> {
  const sessionRefresh = localStorage.getItem(refreshTokenKey);
  const accessAtStart = getAccessToken();
  let response = await send(path, init, authenticated);
  if (response.status === 401 && authenticated
    && sessionRefresh === localStorage.getItem(refreshTokenKey)) {
    // A parallel request may already have refreshed the access token.
    const refreshedToken = accessAtStart !== getAccessToken() && getAccessToken()
      ? getAccessToken() : await refreshAccessToken();
    if (refreshedToken) {
      const headers = new Headers(init.headers);
      headers.set('Authorization', `Bearer ${refreshedToken}`);
      response = await send(path, { ...init, headers }, false);
    }
    if ((!refreshedToken || response.status === 401)
      && sessionRefresh === localStorage.getItem(refreshTokenKey)) expireSession();
  }

  if (!response.ok) {
    const bodyText = await response.text();
    let body: unknown = bodyText;
    try {
      body = bodyText ? JSON.parse(bodyText) : null;
    } catch {
      body = bodyText;
    }
    const error = errorMessage(body, response.status);
    if (response.status === 403) {
      const message = /quyền|permission/i.test(error.message)
        ? error.message
        : `Không đủ quyền thực hiện thao tác này. ${error.message}`;
      throw new ApiError(message, 403, error.code, error.fieldErrors);
    }
    throw new ApiError(error.message, response.status, error.code, error.fieldErrors);
  }

  if (response.status === 204) return undefined as T;
  return parseResponse(response);
}

export const apiGet = <T>(path: string) => request<T>(path);
export const apiGetBlob = (path: string) => request<Blob>(path, {}, true, (response) => response.blob());
export const apiGetPublic = <T>(path: string, init: RequestInit = {}) => request<T>(path, init, false);
export const apiPost = <T>(path: string, payload: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(payload) });
export const apiPostPublic = <T>(path: string, payload: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(payload) }, false);
export const apiPostForm = <T>(path: string, payload: FormData) => request<T>(path, { method: 'POST', body: payload });
export const apiPatch = <T>(path: string, payload: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(payload) });
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' });
