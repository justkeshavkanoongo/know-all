import type { Metadata } from "next";

import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Know It All — Learn with curiosity",
    template: "%s | Know It All",
  },
  description: "A thoughtful place to explore language, literature, psychology and philosophy.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <SiteHeader />
        {children}
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-7xl flex-col gap-2 px-5 py-7 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
            <span>Know It All</span>
            <span>A thoughtful beginning for lifelong learning.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
