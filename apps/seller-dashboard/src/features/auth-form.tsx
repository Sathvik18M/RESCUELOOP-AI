"use client";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import Image from "next/image";
import { Moon, Sun } from "lucide-react";
import { RotatingGlobe } from "@/components/RotatingGlobe";

export function AuthForm({
  title,
  description,
  onSubmit,
  children,
}: {
  title: string;
  description: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}) {
  const [theme, setTheme] = useState<"light" | "dark" | null>(null);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-color-scheme: dark)");
    const followSystem = () => setTheme(preference.matches ? "dark" : "light");
    followSystem();
    preference.addEventListener("change", followSystem);
    return () => preference.removeEventListener("change", followSystem);
  }, []);
  return (
    <main className="login-page" data-theme={theme ?? undefined}>
      <div className="login-form">
        <button
          className="login-theme-toggle"
          type="button"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}
          title={theme === "dark" ? "Use light theme" : "Use dark theme"}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <form onSubmit={onSubmit}>
          <Image
            className="login-logo"
            src="/brand/rescueloop-logo.png"
            alt="RescueLoop AI — customer care, full circle"
            width={1254}
            height={1254}
            sizes="(max-width: 720px) 144px, (max-height: 760px) 152px, 180px"
            preload
          />
          <span className="eyebrow">SELLER PORTAL</span>
          <h1>{title}</h1>
          <p>{description}</p>
          {children}
        </form>
      </div>
      <aside className="login-visual" aria-label="Care that comes full circle">
        <RotatingGlobe />
        <p className="login-visual-caption">Care that comes full circle.</p>
      </aside>
    </main>
  );
}
