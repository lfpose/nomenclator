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

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "APIError";
    this.code = code;
    this.status = status;
  }
}

/**
 * Parse error envelope from response
 * Backend returns: { detail: { error: { code, message } } }
 */
async function parseErrorResponse(response: Response): Promise<APIError> {
  let data: any;
  try {
    data = await response.json();
  } catch {
    throw new APIError("unknown_error", "Failed to parse error response", response.status);
  }

  // Handle FastAPI default error format
  if (data.detail && typeof data.detail === "string") {
    throw new APIError("unknown_error", data.detail, response.status);
  }

  // Handle our structured error format
  if (data.detail?.error?.code && data.detail?.error?.message) {
    throw new APIError(data.detail.error.code, data.detail.error.message, response.status);
  }

  // Handle unknown format
  throw new APIError("unknown_error", "An unknown error occurred", response.status);
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
 * Exported API object for easy imports
 */
export const api = {
  get,
  post,
  postForm,
};
