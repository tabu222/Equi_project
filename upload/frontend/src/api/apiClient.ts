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

export function saveSession(access: string, refresh: string): void {
  localStorage.setItem(accessTokenKey, access);
  localStorage.setItem(refreshTokenKey, refresh);
}

export function clearSession(): void {
  localStorage.removeItem(accessTokenKey);
  localStorage.removeItem(refreshTokenKey);
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
  if (typeof value === 'string' && value) return { message: value, fieldErrors: {} };
  return { message: `Yêu cầu thất bại (HTTP ${status}).`, fieldErrors: {} };
}

async function send(path: string, init: RequestInit, authenticated: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body !== undefined) headers.set('Content-Type', 'application/json');
  const token = authenticated ? getAccessToken() : null;
  if (token) headers.set('Authorization', `Bearer ${token}`);

  try {
    return await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : 'Không thể kết nối API.');
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem(refreshTokenKey);
  if (!refresh) return null;

  const response = await send('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh }),
  }, false);
  if (!response.ok) return null;
  const body = await response.json() as { access?: unknown };
  if (typeof body.access !== 'string' || !body.access) return null;
  localStorage.setItem(accessTokenKey, body.access);
  return body.access;
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  let response = await send(path, init, authenticated);
  if (response.status === 401 && authenticated && getAccessToken()) {
    let refreshedToken: string | null;
    try {
      refreshedToken = await refreshAccessToken();
    } catch {
      clearSession();
      window.dispatchEvent(new Event('equi:session-expired'));
      throw new ApiError('Không thể gia hạn phiên đăng nhập. Vui lòng đăng nhập lại.', 401);
    }
    if (refreshedToken) {
      const headers = new Headers(init.headers);
      headers.set('Authorization', `Bearer ${refreshedToken}`);
      response = await send(path, { ...init, headers }, false);
      if (response.status === 401) {
        clearSession();
        window.dispatchEvent(new Event('equi:session-expired'));
      }
    } else {
      clearSession();
      window.dispatchEvent(new Event('equi:session-expired'));
    }
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
  return response.json() as Promise<T>;
}

export const apiGet = <T>(path: string) => request<T>(path);
export const apiGetPublic = <T>(path: string) => request<T>(path, {}, false);
export const apiPost = <T>(path: string, payload: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(payload) });
export const apiPostPublic = <T>(path: string, payload: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(payload) }, false);
export const apiPatch = <T>(path: string, payload: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(payload) });
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' });
