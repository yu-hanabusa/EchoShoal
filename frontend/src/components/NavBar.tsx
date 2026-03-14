import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Home" },
  { to: "/documents", label: "Documents" },
  { to: "/graph", label: "Knowledge Graph" },
];

export default function NavBar() {
  const location = useLocation();

  return (
    <nav style={{
      borderBottom: "1px solid #e5e7eb",
      backgroundColor: "#ffffff",
      padding: "0 2rem",
    }}>
      <div style={{
        maxWidth: "1200px",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        height: "3.5rem",
        gap: "2rem",
      }}>
        <Link to="/" style={{
          fontWeight: 700,
          fontSize: "1.125rem",
          color: "#1e293b",
          textDecoration: "none",
        }}>
          EchoShoal
        </Link>

        <div style={{ display: "flex", gap: "0.25rem" }}>
          {NAV_ITEMS.map(({ to, label }) => {
            const isActive = location.pathname === to ||
              (to !== "/" && location.pathname.startsWith(to));
            return (
              <Link
                key={to}
                to={to}
                style={{
                  padding: "0.5rem 0.75rem",
                  borderRadius: "4px",
                  fontSize: "0.875rem",
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? "#4f46e5" : "#6b7280",
                  backgroundColor: isActive ? "#eef2ff" : "transparent",
                  textDecoration: "none",
                }}
              >
                {label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
