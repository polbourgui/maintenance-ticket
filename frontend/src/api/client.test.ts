import { ApiError, errorMessage, toApiError } from "./client";

describe("toApiError", () => {
  it("keeps business messages from the API", () => {
    expect(toApiError(422, { detail: "A reason (comment) is required" }).message).toBe(
      "A reason (comment) is required",
    );
  });

  it("formats validation errors with the field path", () => {
    const error = toApiError(422, {
      detail: [{ loc: ["body", "location", "room"], msg: "Field required" }],
    });
    expect(error.message).toBe("Données invalides — location.room : Field required");
  });

  it("uses generic French messages for auth errors", () => {
    expect(toApiError(403, { detail: "You are not allowed" }).message).toBe(
      "Vous n'avez pas les droits pour cette action.",
    );
    expect(toApiError(429, null).message).toContain("Trop de tentatives");
  });

  it("explains server-side failures instead of a generic message", () => {
    expect(toApiError(502, null).message).toContain("backend (uvicorn) est démarré");
    expect(toApiError(500, null).message).toContain("terminal du backend");
  });

  it("describes network failures", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toBe("Impossible de joindre le serveur.");
    expect(errorMessage(new ApiError(404, "Introuvable"))).toBe("Introuvable");
  });
});
