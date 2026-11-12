import "./globals.css";

export const metadata = {
  title: "CommonTable",
  description:
    "Restaurant prices. Affordable delivery. One smarter local network.",
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
