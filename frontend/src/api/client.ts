import createClient from "openapi-fetch";

import type { paths } from "./schema";
import { authFetch } from "./session";

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => authFetch(request),
});

/** Error raised for any non-2xx API answer, with a user-facing French message. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  401: "Votre session a expiré, veuillez vous reconnecter.",
  403: "Vous n'avez pas les droits pour cette action.",
  404: "Élément introuvable.",
  409: "Conflit : l'élément existe déjà ou a été modifié entre-temps. Rechargez la page.",
  413: "Fichier trop volumineux.",
  429: "Trop de tentatives. Réessayez dans quelques minutes.",
};

type ValidationItem = { loc?: (string | number)[]; msg?: string };

export function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && status !== 401 && status !== 403) {
    return new ApiError(status, detail);
  }
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationItem[]).map((item) => {
      const field = item.loc?.filter((p) => p !== "body").join(".");
      return field ? `${field} : ${item.msg ?? "invalide"}` : (item.msg ?? "invalide");
    });
    return new ApiError(status, `Données invalides — ${parts.join(" ; ")}`);
  }
  return new ApiError(status, STATUS_MESSAGES[status] ?? "Une erreur inattendue est survenue.");
}

/** Unwrap an openapi-fetch result, throwing ApiError on failure. */
export async function call<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw toApiError(response.status, error);
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Impossible de joindre le serveur.";
}
