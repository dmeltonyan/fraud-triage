import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { REPO_URL } from "@/lib/project-facts";
import Nav from "./nav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Fraud Triage",
  description:
    "A fraud model scores card transactions; a cost-based policy decides to approve, review or block them under a daily review budget. Simulated data.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <div role="note" className="bg-accent-light px-4 py-2 text-center text-sm text-accent">
          Simulated data. Decisions here are for demonstration only.
        </div>
        <header className="border-b border-line">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-3">
            <Link href="/" className="leading-tight">
              <span className="block text-lg font-semibold">Fraud Triage</span>
              <span className="block text-xs text-muted">Cost-based fraud review</span>
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-5xl flex-wrap justify-between gap-2 px-4 py-4 text-sm text-muted">
            <span>Built by David Meltonyan</span>
            <a href={REPO_URL} className="hover:text-foreground">
              Source code and design decisions on GitHub
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
