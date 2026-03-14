import { Link } from "react-router-dom";

export default function NavBar() {
  return (
    <nav className="border-b border-border bg-surface-0 px-4">
      <div className="max-w-5xl mx-auto flex items-center h-14 gap-4">
        <Link
          to="/"
          className="text-lg font-bold text-brand tracking-tight hover:opacity-80 transition-opacity"
        >
          EchoShoal
        </Link>
        <span className="text-xs text-text-tertiary">
          IT Labor Market Simulator
        </span>
      </div>
    </nav>
  );
}
