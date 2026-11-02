"use client";

import { Film, ImageOff, Loader2 } from "lucide-react";
import { useAssetUrl } from "./hooks";
import { cn } from "@/lib/utils";
import type { Asset } from "@/lib/social-api";

/** Authenticated thumbnail — fetches the file as a blob (the API needs the JWT header). */
export default function AssetThumb({ asset, className, size = "md" }: { asset: Pick<Asset, "id" | "media_type" | "alt_text" | "original_name" | "mime">; className?: string; size?: "sm" | "md" | "lg" }) {
  const { url, failed } = useAssetUrl(asset.id);
  const dims = size === "sm" ? "h-12 w-12" : size === "lg" ? "h-48 w-full" : "h-24 w-24";
  const alt = asset.alt_text || asset.original_name || "נכס";
  return (
    <div className={cn("relative grid shrink-0 place-items-center overflow-hidden rounded-lg border border-border bg-black/40", dims, className)}>
      {failed ? <ImageOff size={18} className="text-muted-foreground" aria-label="הקובץ לא נטען" />
        : !url ? <Loader2 size={16} className="animate-spin text-muted-foreground" aria-label="טוען" />
        : asset.media_type === "video" ? (
          <>
            <video src={url} muted playsInline className="h-full w-full object-cover" aria-label={alt} />
            <Film size={14} className="absolute bottom-1 end-1 text-white drop-shadow" aria-hidden />
          </>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={alt} className="h-full w-full object-cover" />
        )}
    </div>
  );
}
