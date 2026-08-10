import type { Metadata } from "next";
import "./globals.css";

const title = "观宇芯算研发部周报";
const description = "观宇芯算研发部每周技术情报、论文精读与一手来源核验";
const socialImage =
  "https://seespace-lab.github.io/og.png";

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
