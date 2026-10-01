"use client";

interface Props {
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  risk: "LOW" | "HIGH";
  onApprove: (requestId: string) => void;
  onDeny: (requestId: string) => void;
}

export default function ApprovalModal({ requestId, toolName, toolInput, risk, onApprove, onDeny }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-card border border-border rounded-xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${risk === "HIGH" ? "bg-red-500" : "bg-yellow-500"}`} />
            <span className="font-mono text-sm font-bold tracking-wider">TOOL APPROVAL REQUIRED</span>
          </div>
          <span className={`font-mono text-xs px-2 py-0.5 rounded border ${
            risk === "HIGH"
              ? "text-red-500 border-red-500/40 bg-red-500/10"
              : "text-yellow-500 border-yellow-500/40 bg-yellow-500/10"
          }`}>
            {risk} RISK
          </span>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          <div>
            <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-1">Tool</p>
            <p className="font-mono text-sm font-medium">{toolName}</p>
          </div>
          {Object.keys(toolInput).length > 0 && (
            <div>
              <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest mb-1">Parameters</p>
              <pre className="font-mono text-xs bg-muted rounded-lg p-3 overflow-auto max-h-40 text-foreground/80 whitespace-pre-wrap">
                {JSON.stringify(toolInput, null, 2)}
              </pre>
            </div>
          )}
          <p className="font-mono text-xs text-muted-foreground">
            The agent wants to run this tool. Review the parameters and approve or deny.
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-2 px-5 py-4 border-t border-border bg-muted/20">
          <button
            onClick={() => onDeny(requestId)}
            className="flex-1 px-4 py-2 border border-border rounded-lg font-mono text-sm hover:bg-muted/50 transition-colors"
          >
            DENY ✕
          </button>
          <button
            onClick={() => onApprove(requestId)}
            className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-mono text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            APPROVE ✓
          </button>
        </div>
      </div>
    </div>
  );
}
