import { useEffect, useState } from "react";
import { Outlet } from "@tanstack/react-router";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
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
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        {authState === "checking" && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        )}
        {authState === "unauthenticated" && (
          <div className="flex items-center justify-center min-h-[60vh]">
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
      <Footer />
    </div>
  );
}
