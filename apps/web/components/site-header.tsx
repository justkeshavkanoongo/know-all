import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-line bg-paper/95">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-5 sm:px-8 lg:px-12">
        <Link
          aria-label="Know It All home"
          className="font-display text-xl font-semibold tracking-tight text-navy sm:text-2xl"
          href="/"
        >
          know it all<span className="text-sage">.</span>
        </Link>
        <nav aria-label="Main navigation" className="flex items-center gap-5 sm:gap-8">
          <Link className="nav-link" href="/">
            Explore courses
          </Link>
          <span className="hidden text-sm text-muted sm:inline">A place for curious minds</span>
        </nav>
      </div>
    </header>
  );
}
