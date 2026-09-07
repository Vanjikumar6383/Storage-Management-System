const BASE_URL = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = 'ApiError';
  }
}

export async function fetchJson<T>(
  endpoint: string,
  options: RequestInit = {},
  orgId?: string
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', 'application/json');

  let url = `${BASE_URL}${endpoint}`;

  if (orgId) {
    const separator = url.includes('?') ? '&' : '?';
    url = `${url}${separator}organization_id=${encodeURIComponent(orgId)}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = await response.text();
    }
    const message =
      typeof errorData === 'object' && errorData?.detail
        ? errorData.detail
        : `API Request Failed (${response.status})`;
    throw new ApiError(response.status, message, errorData);
  }

  return response.json() as Promise<T>;
}
