"use client";

import { useState } from "react";
import { AlertTriangle, Key, Loader2, Shield } from "lucide-react";
import { api } from "@/hooks/use-api";
import { toast } from "@/components/common/toast";

export function EncryptionKeyRotation() {
  const [showDialog, setShowDialog] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [rotating, setRotating] = useState(false);

  const handleRotate = async () => {
    if (!newKey.trim()) {
      toast.error("Please enter a new Fernet key");
      return;
    }
    setRotating(true);
    try {
      const result = await api.post<{ rotated: number; message: string }>("/api/v1/admin/rotate-encryption-key", { new_key: newKey });
      toast.success(result.message);
      setShowDialog(false);
      setNewKey("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Key rotation failed");
    }
    setRotating(false);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-primary/10 p-3">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-foreground">Encryption Key Rotation</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Rotate the Fernet encryption key used to encrypt all stored database connection credentials.
              This will re-encrypt every credential with the new key atomically.
            </p>
            <button
              onClick={() => setShowDialog(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Key className="h-4 w-4" /> Rotate Key
            </button>
          </div>
        </div>
      </div>

      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              <h3 className="text-lg font-semibold text-foreground">Rotate Encryption Key</h3>
            </div>

            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 mb-4">
              <p className="text-sm text-yellow-700 dark:text-yellow-400">
                This will re-encrypt all connection credentials with the new key.
                After rotation, you must update the <code className="font-mono text-xs">FERNET_KEY</code> environment
                variable to the new key value. Failure to do so will make credentials unreadable.
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-medium text-muted-foreground mb-1">New Fernet Key</label>
              <input
                type="text"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="Enter new Fernet key (base64-encoded 32-byte key)"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm font-mono text-foreground"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Generate with: <code>python -c &quot;from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())&quot;</code>
              </p>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowDialog(false); setNewKey(""); }}
                className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleRotate}
                disabled={!newKey.trim() || rotating}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {rotating ? <Loader2 className="h-4 w-4 animate-spin" /> : "Rotate Key"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
