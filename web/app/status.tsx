// Messages shared by pages that load data from the API.

export function Loading({ what, slow }: { what: string; slow: boolean }) {
  return (
    <p className="text-muted" role="status">
      Loading {what}…
      {slow && (
        <span className="mt-2 block">
          The demo server is probably waking up after being idle. This can take up to a minute the first time.
        </span>
      )}
    </p>
  );
}

export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-line p-4">
      <p>{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white"
      >
        Retry
      </button>
    </div>
  );
}
