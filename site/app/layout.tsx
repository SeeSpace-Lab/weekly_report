import type { Metadata } from "next";
import "./globals.css";

const title = "观宇芯算研发部周报";
const description = "2026-W32 研发周报公开只读审核：16 条精选研究情报与一手来源核验";
const socialImage =
  "https://guanyu-weekly-w32-review.dccctrue.chatgpt.site/og-w32-v2.png";

export const metadata: Metadata = {
  title,
  description,
  openGraph: {
    title,
    description,
    type: "website",
    images: [{ url: socialImage, width: 1536, height: 1024 }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: [socialImage],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
