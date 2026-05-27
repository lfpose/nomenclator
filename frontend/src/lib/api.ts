/**
 * API client wrapper for Nomenclator backend
 * Handles session cookies, JSON parsing, and error envelope extraction
 */

export interface APIErrorDetail {
  code: string;
  message: string;
}

export interface APIErrorResponse {
  detail: {
    error: APIErrorDetail;
  };
}

export class APIError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = "APIError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/**
 * Parse error envelope from response
 * Backend returns: { detail: { error: { code, message } } }
 */
async function parseErrorResponse(response: Response): Promise<APIError> {
  let raw = "";
  let data: any = null;
  try {
    raw = await response.text();
    data = raw ? JSON.parse(raw) : null;
  } catch {
    // Non-JSON body: surface the text directly so the dev sees what came back.
    throw new APIError(
      "unknown_error",
      raw.slice(0, 500) || `HTTP ${response.status}`,
      response.status,
      { raw_body: raw.slice(0, 2000), url: response.url }
    );
  }

  // Our structured envelope (current backend): { error: { code, message, details } }
  if (data?.error?.code) {
    return new APIError(
      data.error.code,
      data.error.message || `HTTP ${response.status}`,
      response.status,
      { ...(data.error.details || {}), url: response.url }
    );
  }

  // Legacy / wrapped: { detail: { error: { ... } } }
  if (data?.detail?.error?.code) {
    return new APIError(
      data.detail.error.code,
      data.detail.error.message || `HTTP ${response.status}`,
      response.status,
      { ...(data.detail.error.details || {}), url: response.url }
    );
  }

  // FastAPI default: { detail: "..." } or { detail: [...] }
  if (data?.detail) {
    const msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    return new APIError("http_error", msg, response.status, { raw: data, url: response.url });
  }

  return new APIError(
    "unknown_error",
    `HTTP ${response.status}`,
    response.status,
    { raw: data, raw_body: raw.slice(0, 2000), url: response.url }
  );
}

/**
 * Make a GET request with session cookie support
 */
export async function get<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  return response.json();
}

/**
 * Make a POST request with JSON body and session cookie support
 */
export async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  return response.json();
}

/**
 * Make a POST request with FormData (for file uploads) and session cookie support
 */
export async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    // Don't set Content-Type for FormData - browser sets it with boundary
    body: formData,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  return response.json();
}

/**
 * Make a POST request to /auth/logout to destroy the session
 */
export async function logout(): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/auth/logout", {});
}

/**
 * Exported API object for easy imports
 */
export const api = {
  get,
  post,
  postForm,
  logout,
};
