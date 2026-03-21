import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SIA",
  description: "AI Web Agent for Enterprise Data Analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="h-full dark">
      <body className={`${inter.className} h-full overflow-hidden bg-slate-50 dark:bg-slate-950 flex text-slate-800 dark:text-slate-200 antialiased`}>
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-[0] h-full overflow-hidden w-full relative bg-slate-50/50 dark:bg-[#0A0D14]">
            <Header />
            <main className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 md:p-6 relative">
              {children}
            </main>
        </div>
      </body>
    </html>
  );
}
