"use client";

import { ChangeEvent, FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AuthTabs, Ripple, TechOrbitDisplay } from "@/components/blocks/modern-animated-sign-in";
import { dbIconsArray } from "@/components/blocks/sign-in-orbit-icons";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { useAuthStore } from "@/stores/auth-store";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type SsoButton = { id: string; label: string; loginUrl: string };

function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || searchParams.get("redirect") || "/";

  const login = useAuthStore((s) => s.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorField, setErrorField] = useState<string | undefined>();
  const [ssoButtons, setSsoButtons] = useState<SsoButton[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/auth/sso/providers`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const body = await res.json();
        if (cancelled) return;
        setSsoButtons(
          (body.providers ?? []).map((p: { id: string; label: string; login_url: string }) => ({
            id: p.id,
            label: p.label,
            loginUrl: p.login_url.startsWith("http") ? p.login_url : `${API_URL}${p.login_url}`,
          })),
        );
      } catch {
        // No SSO providers — local login only.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorField(undefined);
    try {
      const { forcePasswordChange } = await login(email, password);
      if (forcePasswordChange) {
        router.push(`/change-password?next=${encodeURIComponent(next)}`);
      } else {
        router.push(next);
      }
    } catch (err) {
      setErrorField(err instanceof Error ? err.message : "Sign-in failed");
    }
  };

  const formFields = {
    header: "Welcome to Synthia",
    subHeader: "Sign in to access your projects",
    fields: [
      {
        label: "Email",
        required: true,
        type: "email" as const,
        placeholder: "you@ameritas.com",
        onChange: (e: ChangeEvent<HTMLInputElement>) => setEmail(e.target.value),
      },
      {
        label: "Password",
        required: true,
        type: "password" as const,
        placeholder: "Enter your password",
        onChange: (e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value),
      },
    ],
    submitButton: "Sign in",
    errorField,
  };

  return (
    <section className="relative flex max-lg:justify-center min-h-screen">
      {/* Theme toggle — top-right, anchored to the page (not the form column)
          so it sits above both the orbit and the auth form. */}
      <div className="absolute top-4 right-4 z-50">
        <ThemeToggle variant="surface" />
      </div>

      {/* Left — orbit visual */}
      <span className="relative flex flex-col justify-center w-1/2 max-lg:hidden">
        <Ripple mainCircleSize={100} />
        <TechOrbitDisplay iconsArray={dbIconsArray} text="Synthia" />
      </span>

      {/* Right — auth form */}
      <span className="w-1/2 h-[100dvh] flex flex-col justify-center items-center max-lg:w-full max-lg:px-[10%]">
        <AuthTabs
          formFields={formFields}
          ssoButtons={ssoButtons}
          handleSubmit={handleSubmit}
        />
      </span>
    </section>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-background" />}>
      <LoginInner />
    </Suspense>
  );
}
