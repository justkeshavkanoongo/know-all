"use client";

import { useState } from "react";
import Link from "next/link";

export function LessonLink() {
  const [opening, setOpening] = useState(false);

  return (
    <Link
      className="mt-4 inline-flex rounded-sm font-semibold text-navy underline decoration-sage underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-sage"
      href="/lessons/german-a1-greetings"
      onClick={(event) => {
        if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
          setOpening(true);
        }
      }}
      aria-busy={opening}
      aria-live="polite"
    >
      {opening ? "Opening lesson…" : "Read the lesson"}
      <span className="sr-only">: Greetings and introducing yourself</span> →
    </Link>
  );
}
