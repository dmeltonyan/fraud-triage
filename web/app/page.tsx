import { Suspense } from "react";
import QueueView from "./queue-view";

export default function QueuePage() {
  // QueueView reads ?date= from the URL, which Next.js requires to sit inside Suspense.
  return (
    <Suspense fallback={<p className="text-muted">Loading…</p>}>
      <QueueView />
    </Suspense>
  );
}
