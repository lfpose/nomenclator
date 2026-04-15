import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useNotification } from "../src/hooks/useNotification";

const mockRequestPermission = vi.fn();
const mockNotification = vi.fn();

describe("useNotification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock window.Notification as a proper constructor
    global.Notification = Object.assign(function() {
      mockNotification.apply(this, arguments);
    }, {
      permission: "default",
      requestPermission: mockRequestPermission,
    }) as any;
  });

  afterEach(() => {
    // Clean up
    delete (global as any).Notification;
  });

  it("requests permission on first commit", async () => {
    mockRequestPermission.mockResolvedValue("granted");

    const { result } = renderHook(() => useNotification());

    expect(result.current.hasRequestedPermission).toBe(false);
    expect(result.current.permissionState).toBe("default");

    let permission: NotificationPermission;
    await act(async () => {
      permission = await result.current.requestPermission();
    });

    expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    expect(permission).toBe("granted");
    await waitFor(() => {
      expect(result.current.hasRequestedPermission).toBe(true);
    });
    expect(result.current.permissionState).toBe("granted");
  });

  it("fires notification on job complete", async () => {
    // Mock granted permission
    mockRequestPermission.mockResolvedValue("granted");
    Object.defineProperty(Notification, "permission", {
      writable: true,
      value: "granted",
    });

    const { result } = renderHook(() => useNotification());

    // First request permission
    await result.current.requestPermission();

    // Fire notification for completed job
    result.current.notifyJobTerminal("completed", "abc123");

    expect(mockNotification).toHaveBeenCalledTimes(1);
    expect(mockNotification).toHaveBeenCalledWith("Nomenclator — job completed", {
      body: "Job abc123 has completed successfully. Download your results.",
      icon: "/icon-192.png",
    });
  });

  it("no-op if permission denied", async () => {
    // Mock denied permission
    mockRequestPermission.mockResolvedValue("denied");
    Object.defineProperty(Notification, "permission", {
      writable: true,
      value: "denied",
    });

    const { result } = renderHook(() => useNotification());

    // Request permission (will be denied)
    await result.current.requestPermission();

    // Try to fire notification
    result.current.notifyJobTerminal("completed", "abc123");

    expect(mockNotification).not.toHaveBeenCalled();
  });

  it("does not request permission before commit", () => {
    mockRequestPermission.mockResolvedValue("granted");
    Object.defineProperty(Notification, "permission", {
      writable: true,
      value: "default",
    });

    const { result } = renderHook(() => useNotification());

    // Should not request permission automatically
    expect(mockRequestPermission).not.toHaveBeenCalled();
    expect(result.current.hasRequestedPermission).toBe(false);
  });
});
