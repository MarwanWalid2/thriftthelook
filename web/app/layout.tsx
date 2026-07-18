import type { Metadata } from "next";
import { Caveat, Nunito } from "next/font/google";

import "./globals.css";

const nunito = Nunito({
  variable: "--font-nunito",
  subsets: ["latin"],
  weight: ["400", "600", "800"],
});

const caveat = Caveat({
  variable: "--font-caveat",
  subsets: ["latin"],
  weight: ["500", "600"],
});

export const metadata: Metadata = {
  title: "ThriftTheLook | Screenshot the fit. Thrift the look.",
  description: "Build a secondhand look around the outfit that inspired you.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${nunito.variable} ${caveat.variable}`}>{children}</body>
    </html>
  );
}
