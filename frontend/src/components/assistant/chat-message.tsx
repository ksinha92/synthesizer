"use client";

import Link from "next/link";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  actions?: { label: string; href: string }[];
}

export function ChatMessage({ role, content, actions }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <div className={cn(
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
        isUser ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
      )}>
        {isUser ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </div>

      <div className={cn(
        "max-w-[80%] rounded-lg px-3 py-2 text-sm",
        isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
      )}>
        <p className="whitespace-pre-wrap">{content}</p>

        {actions && actions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {actions.map((action, i) => (
              <Link
                key={i}
                href={action.href}
                className="inline-flex items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
              >
                {action.label}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
