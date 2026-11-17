import { useEffect, useState } from "react";

import { authFetch } from "../api/session";

/** <img> for protected files: fetched with the bearer token, displayed through a blob: URL. */
export function AuthImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    authFetch(src)
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        const blob = await response.blob();
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (failed) return <div className={`${className ?? ""} img-placeholder`}>Image indisponible</div>;
  if (!url) return <div className={`${className ?? ""} img-placeholder`} aria-busy="true" />;
  return <img src={url} alt={alt} className={className} />;
}
