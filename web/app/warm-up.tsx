"use client";

import { useEffect } from "react";
import { API_URL } from "@/lib/api";

/** Wakes the free-tier API while the visitor reads the overview, so the queue is ready when they click. */
export default function WarmUp() {
  useEffect(() => {
    fetch(`${API_URL}/health`).catch(() => {}); // the answer doesn't matter
  }, []);
  return null;
}
