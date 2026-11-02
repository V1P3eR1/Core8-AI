import type { Metadata } from "next";
import { Heebo } from "next/font/google";
import SocialShell from "@/components/social/SocialShell";

const heebo = Heebo({ subsets: ["hebrew", "latin"], variable: "--font-heebo" });

export const metadata: Metadata = {
  title: "Core8AI Social Manager",
  description: "ניהול תוכן אינסטגרם — מחקר, רעיונות, יצירה, אישורים ופרסום",
};

export default function SocialLayout({ children }: { children: React.ReactNode }) {
  return (
    <div dir="rtl" lang="he" className={`${heebo.variable} min-h-screen font-[family-name:var(--font-heebo)] antialiased`}>
      <SocialShell>{children}</SocialShell>
    </div>
  );
}
