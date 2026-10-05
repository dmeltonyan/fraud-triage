import type { Action } from "@/lib/api";

// One colour per action, used everywhere: approve green, review amber, block red.
export const ACTION_STYLES: Record<Action, { label: string; text: string; bg: string; bar: string }> = {
  approve: { label: "Approve", text: "text-approve", bg: "bg-approve-light", bar: "bg-approve" },
  review: { label: "Review", text: "text-review", bg: "bg-review-light", bar: "bg-review" },
  block: { label: "Block", text: "text-block", bg: "bg-block-light", bar: "bg-block" },
};

export default function ActionBadge({ action }: { action: Action }) {
  const style = ACTION_STYLES[action];
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${style.bg} ${style.text}`}>
      {style.label}
    </span>
  );
}
