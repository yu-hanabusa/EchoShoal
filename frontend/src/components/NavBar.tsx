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
          Service Business Impact Simulator
        </span>
        <div className="flex-1" />
        <Link
          to="/benchmarks"
          className="text-xs text-text-secondary hover:text-interactive transition-colors"
        >
          Benchmarks
        </Link>
      </div>
    </nav>
  );
}
