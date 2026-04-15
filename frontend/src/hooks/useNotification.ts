import { useCallback, useEffect, useState } from "react";

type TerminalStatus = "completed" | "failed" | "cancelled";

interface UseNotificationReturn {
  requestPermission: () => Promise<NotificationPermission>;
  notifyJobTerminal: (status: TerminalStatus, jobId: string) => void;
  hasRequestedPermission: boolean;
  permissionState: NotificationPermission | "unsupported";
}

export function useNotification(): UseNotificationReturn {
  const [hasRequestedPermission, setHasRequestedPermission] = useState(false);
  const [permissionState, setPermissionState] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );

  const requestPermission = useCallback(async (): Promise<NotificationPermission> => {
    if (typeof Notification === "undefined") {
      return "denied";
    }

    setHasRequestedPermission(true);
    const permission = await Notification.requestPermission();
    setPermissionState(permission);
    return permission;
  }, []);

  const notifyJobTerminal = useCallback((status: TerminalStatus, jobId: string) => {
    if (typeof Notification === "undefined") {
      return;
    }

    if (Notification.permission !== "granted") {
      return;
    }

    const titles: Record<TerminalStatus, string> = {
      completed: "Nomenclator — job completed",
      failed: "Nomenclator — job failed",
      cancelled: "Nomenclator — job cancelled",
    };

    const bodies: Record<TerminalStatus, string> = {
      completed: `Job ${jobId} has completed successfully. Download your results.`,
      failed: `Job ${jobId} has failed. Check the details for more information.`,
      cancelled: `Job ${jobId} was cancelled.`,
    };

    new Notification(titles[status], {
      body: bodies[status],
      icon: "/icon-192.png", // Optional: add icon if available
    });
  }, []);

  useEffect(() => {
    if (typeof Notification !== "undefined" && Notification.permission !== "granted") {
      // Check if permission changed (user might have granted it elsewhere)
      setPermissionState(Notification.permission);
    }
  }, []);

  return {
    requestPermission,
    notifyJobTerminal,
    hasRequestedPermission,
    permissionState,
  };
}


