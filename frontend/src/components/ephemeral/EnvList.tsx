"use client";

import { EnvRow } from "./EnvRow";
import type { EphemeralEnv } from "./types";

export function EnvList({
  envs,
  now,
  onRevoke,
}: {
  envs: EphemeralEnv[];
  now: number;
  onRevoke: (env: EphemeralEnv) => void;
}) {
  return (
    <ul className="divide-y divide-border">
      {envs.map((env) => (
        <EnvRow key={env.id} env={env} now={now} onRevoke={() => onRevoke(env)} />
      ))}
    </ul>
  );
}
