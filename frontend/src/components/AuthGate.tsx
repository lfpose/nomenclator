import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PasswordForm } from "./PasswordForm";

interface AuthGateProps {
  children: React.ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await api.get("/me");
        setIsAuthenticated(true);
      } catch (err) {
        setIsAuthenticated(false);
      }
    };

    checkAuth();
  }, []);

  if (isAuthenticated === null) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <h1 className="text-3xl font-serif">nomenclator</h1>
            <p className="mt-2 text-muted-foreground">
              Sign in to continue
            </p>
          </div>
          <PasswordForm onSuccess={() => setIsAuthenticated(true)} />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
