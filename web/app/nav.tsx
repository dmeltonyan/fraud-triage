"use client"; // needs the current URL to highlight the active link

import Link from "next/link";
import { usePathname } from "next/navigation";
import { REPO_URL } from "@/lib/project-facts";

const LINKS = [
  { href: "/", label: "Overview", matches: (path: string) => path === "/" },
  // Case pages are opened from the queue, so they count as "Try it".
  { href: "/queue", label: "Try it", matches: (path: string) => path === "/queue" || path.startsWith("/case/") },
  { href: "/results", label: "Results", matches: (path: string) => path.startsWith("/results") },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
      {LINKS.map(({ href, label, matches }) => {
        const active = matches(pathname);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-2 text-sm font-medium ${
              active ? "bg-accent-light text-accent" : "text-muted hover:text-foreground"
            }`}
          >
            {label}
          </Link>
        );
      })}
      <a href={REPO_URL} className="rounded-md px-3 py-2 text-sm font-medium text-muted hover:text-foreground">
        GitHub ↗
      </a>
    </nav>
  );
}
