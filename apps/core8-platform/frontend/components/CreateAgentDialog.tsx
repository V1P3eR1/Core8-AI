"use client";

import { useState } from "react";
import { createAgent } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

const MODELS = [
  { value: "claude-sonnet-4-6", label: "Sonnet 4.6 (recommended)" },
  { value: "claude-haiku-4-5-20251001", label: "Haiku 4.5 (fast)" },
  { value: "claude-opus-4-7", label: "Opus 4.7 (powerful)" },
];

interface Props {
  onCreated: (agent: { id: string; name: string; description: string }) => void;
}

export default function CreateAgentDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [model, setModel] = useState("claude-sonnet-4-6");

  const reset = () => {
    setName("");
    setDescription("");
    setSystemPrompt("");
    setModel("claude-sonnet-4-6");
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createAgent({
        name: name.trim(),
        description: description.trim(),
        system_prompt: systemPrompt.trim(),
        model,
      });
      onCreated({ id: created.id, name: created.name, description: description.trim() });
      setOpen(false);
      reset();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
      <DialogTrigger
        className="w-full text-left px-4 py-2 font-mono text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors border-t border-border flex items-center gap-2"
      >
        <span className="text-base leading-none">+</span> NEW AGENT
      </DialogTrigger>

      <DialogContent className="sm:max-w-lg font-mono">
        <DialogHeader>
          <DialogTitle className="font-mono tracking-widest text-sm">NEW AGENT</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {/* Name */}
          <div className="space-y-1.5">
            <Label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Name <span className="text-destructive">*</span>
            </Label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lead Manager"
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground"
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Description
            </Label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this agent do?"
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground"
            />
          </div>

          {/* System Prompt */}
          <div className="space-y-1.5">
            <Label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              System Prompt
            </Label>
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="You are a specialized AI agent for Core8-AI. Your job is..."
              className="font-mono text-sm min-h-[120px] resize-y"
            />
          </div>

          {/* Model */}
          <div className="space-y-1.5">
            <Label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              Model
            </Label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-primary"
            >
              {MODELS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          {/* Error */}
          {error && (
            <p className="text-xs text-destructive font-mono">{error}</p>
          )}

          {/* Actions */}
          <div className="flex gap-2 justify-end pt-2">
            <Button
              type="button"
              variant="ghost"
              className="font-mono text-xs"
              onClick={() => setOpen(false)}
              disabled={loading}
            >
              CANCEL
            </Button>
            <Button
              type="submit"
              className="font-mono text-xs"
              disabled={loading || !name.trim()}
            >
              {loading ? "CREATING..." : "CREATE AGENT →"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
