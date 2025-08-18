export const metadata = {
  title: "JIT Warm Dashboard",
  description: "Just-in-time Lambda warm orchestration dashboard",
};

import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-gradient-to-b from-slate-950 via-slate-900 to-slate-900 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
