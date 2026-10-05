"use client"; // needs the current URL to highlight the active link

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Review queue" },
  { href: "/results", label: "Results" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex gap-1">
      {LINKS.map(({ href, label }) => {
        // The queue link also covers case pages, which are opened from the queue.
        const active = href === "/" ? pathname === "/" || pathname.startsWith("/case/") : pathname.startsWith(href);
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
    </nav>
  );
}
