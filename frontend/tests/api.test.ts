/**
 * Tests for API client wrapper
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, get, post, postForm, APIError } from "../src/lib/api";

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockClear();
});

describe("api.get", () => {
  it("get returns parsed JSON on 200", async () => {
    const mockData = { ok: true, data: "test" };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await get("/api/test");
    expect(result).toEqual(mockData);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
      })
    );
  });

  it("get throws APIErrorResponse on 4xx", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({
        detail: {
          error: {
            code: "unauthenticated",
            message: "Session required.",
          },
        },
      }),
    });

    await expect(get("/api/protected")).rejects.toThrow(APIError);
  });

  it("error has code and status fields", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        detail: {
          error: {
            code: "job_not_found",
            message: "Job not found",
          },
        },
      }),
    });

    try {
      await get("/api/jobs/missing");
      expect.fail("Should have thrown APIError");
    } catch (error) {
      expect(error).toBeInstanceOf(APIError);
      expect((error as APIError).code).toBe("job_not_found");
      expect((error as APIError).status).toBe(404);
      expect((error as APIError).message).toBe("Job not found");
    }
  });
});

describe("api.post", () => {
  it("post sends JSON body", async () => {
    const mockResponse = { success: true };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    const requestBody = { title: "Test", value: 123 };
    const result = await post("/api/create", requestBody);

    expect(result).toEqual(mockResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/create",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      })
    );
  });

  it("credentials include is set", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
    });

    await get("/api/test");

    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1];
    expect(options).toHaveProperty("credentials");
    expect(options.credentials).toBe("include");
  });
});

describe("api.postForm", () => {
  it("postForm sends FormData", async () => {
    const mockResponse = { job_id: "abc123" };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    });

    const formData = new FormData();
    formData.append("file", new Blob(["test data"]), "test.csv");
    formData.append("threshold", "85");

    const result = await postForm("/api/upload", formData);

    expect(result).toEqual(mockResponse);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/upload",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: formData,
      })
    );

    // Ensure Content-Type is not set (let browser set with boundary)
    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1];
    expect(options.headers).toBeUndefined();
  });
});

describe("APIError class", () => {
  it("creates error with code, message, and status", () => {
    const error = new APIError("test_error", "Test message", 400);

    expect(error.name).toBe("APIError");
    expect(error.code).toBe("test_error");
    expect(error.message).toBe("Test message");
    expect(error.status).toBe(400);
  });

  it("is instanceof Error", () => {
    const error = new APIError("test", "message", 500);
    expect(error).toBeInstanceOf(Error);
  });
});

describe("error envelope parsing edge cases", () => {
  it("handles plain string detail (FastAPI default)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        detail: "Validation error",
      }),
    });

    try {
      await get("/api/test");
      expect.fail("Should have thrown APIError");
    } catch (error) {
      expect(error).toBeInstanceOf(APIError);
      expect((error as APIError).code).toBe("unknown_error");
      expect((error as APIError).message).toBe("Validation error");
    }
  });

  it("handles non-JSON response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("Invalid JSON");
      },
    });

    try {
      await get("/api/test");
      expect.fail("Should have thrown APIError");
    } catch (error) {
      expect(error).toBeInstanceOf(APIError);
      expect((error as APIError).code).toBe("unknown_error");
      expect((error as APIError).message).toBe("Failed to parse error response");
    }
  });

  it("handles unknown error format", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        something: "else",
      }),
    });

    try {
      await get("/api/test");
      expect.fail("Should have thrown APIError");
    } catch (error) {
      expect(error).toBeInstanceOf(APIError);
      expect((error as APIError).code).toBe("unknown_error");
      expect((error as APIError).message).toBe("An unknown error occurred");
    }
  });
});
