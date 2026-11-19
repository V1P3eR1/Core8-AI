"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/social-api";
import { errorMessage } from "./toast";

/** Load data on mount (and when `deps` change) with loading/error state and a `reload()` handle. */
export function useLoad<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loaderRef = useRef(loader);
  useEffect(() => { loaderRef.current = loader; });

  useEffect(() => {
    let active = true;
    loader()
      .then((d) => { if (active) { setData(d); setError(null); } })
      .catch((e) => { if (active) setError(errorMessage(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const d = await loaderRef.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, setData, loading, error, reload };
}

/** Fetch an authenticated asset file as an object URL (revoked on unmount / id change). */
export function useAssetUrl(assetId: string | null | undefined) {
  const [state, setState] = useState<{ id: string; url: string | null; failed: boolean } | null>(null);
  useEffect(() => {
    if (!assetId) return;
    let active = true;
    let objectUrl: string | null = null;
    api.assets.file(assetId)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setState({ id: assetId, url: objectUrl, failed: false });
      })
      .catch(() => { if (active) setState({ id: assetId, url: null, failed: true }); });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [assetId]);
  const current = assetId && state?.id === assetId ? state : null;
  return { url: current?.url ?? null, failed: current?.failed ?? false };
}

/** Wrap an async action with a busy flag. */
export function useBusy() {
  const [busy, setBusy] = useState<string | null>(null);
  const run = useCallback(async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try { await fn(); } finally { setBusy(null); }
  }, []);
  return { busy, run };
}
