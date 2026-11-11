import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "RescueLoop — Seller Workspace",
  description:
    "Thoughtful customer care, connected commerce. Manage conversations, approvals, policies and fulfillment.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
