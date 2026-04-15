import { Outlet, Link } from "@tanstack/react-router";

export default function RootLayout() {
  return (
    <div>
      <nav>
        <Link to="/">Tool</Link>{" | "}
        <Link to="/about">About</Link>{" | "}
        <Link to="/docs">Docs</Link>
      </nav>
      <Outlet />
    </div>
  );
}