import { useEffect, useState } from "react";
import { Outlet } from "@tanstack/react-router";
import { Header } from "@/components/Header";
import { PasswordForm } from "@/components/PasswordForm";
import { api } from "@/lib/api";

type AuthState = "checking" | "authenticated" | "unauthenticated";

export default function RootLayout() {
  const [authState, setAuthState] = useState<AuthState>("checking");

  useEffect(() => {
    api.get("/me")
      .then(() => setAuthState("authenticated"))
      .catch(() => setAuthState("unauthenticated"));
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header />
      <main className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {authState === "checking" && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        )}
        {authState === "unauthenticated" && (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full max-w-sm space-y-6 px-4">
              <div className="text-center space-y-2">
                <h1 className="text-3xl font-serif">Nomenclator</h1>
                <p className="text-sm text-muted-foreground">Sign in to continue</p>
              </div>
              <PasswordForm onSuccess={() => setAuthState("authenticated")} />
            </div>
          </div>
        )}
        {authState === "authenticated" && <Outlet />}
      </main>
    </div>
  );
}
