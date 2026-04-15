import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Link } from "@tanstack/react-router";
import { api } from "@/lib/api";
import { useState } from "react";

export function Header() {
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await api.logout();
      // Reload the page to clear any cached state and let AuthGate re-check auth
      window.location.reload();
    } catch (error) {
      console.error("Logout failed:", error);
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center px-4 max-w-6xl mx-auto">
        {/* Wordmark on the left */}
        <div className="mr-auto flex items-center">
          <h1 className="font-serif text-xl font-semibold tracking-tight">nomenclator</h1>
        </div>

        {/* Nav links in the center */}
        <nav className="flex items-center space-x-6">
          <Link to="/" className="text-sm font-medium transition-colors hover:text-primary">
            Tool
          </Link>
          <Link to="/about" className="text-sm font-medium transition-colors hover:text-primary">
            About
          </Link>
          <Link to="/docs" className="text-sm font-medium transition-colors hover:text-primary">
            Docs
          </Link>
        </nav>

        {/* Theme toggle and logout on the right */}
        <div className="ml-auto flex items-center space-x-2">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            disabled={isLoggingOut}
            aria-label="Logout"
          >
            <LogOut className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </header>
  );
}
