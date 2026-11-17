import { authFetch, getAccessToken, login, refreshSession, setAccessToken } from "./session";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const pair = (token: string) => ({
  access_token: token,
  token_type: "bearer",
  expires_at: "",
  refresh_token: "ignored-by-the-browser-app",
  refresh_expires_at: "",
});

describe("session", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    setAccessToken(null);
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("keeps the access token in memory and sends it as bearer", async () => {
    fetchMock.mockResolvedValueOnce(json(200, pair("A1")));
    await login("a@example.org", "pw");
    expect(getAccessToken()).toBe("A1");

    fetchMock.mockResolvedValueOnce(json(200, {}));
    await authFetch("http://localhost/api/v1/users/me");
    const request = fetchMock.mock.calls[1]![0] as Request;
    expect(request.headers.get("Authorization")).toBe("Bearer A1");
  });

  it("refreshes once on 401 and replays the request", async () => {
    setAccessToken("expired");
    fetchMock
      .mockResolvedValueOnce(json(401, {}))
      .mockResolvedValueOnce(json(200, pair("A2")))
      .mockResolvedValueOnce(json(200, { ok: true }));
    const response = await authFetch("http://localhost/api/v1/tickets");
    expect(response.status).toBe(200);
    expect(getAccessToken()).toBe("A2");
    const replay = fetchMock.mock.calls[2]![0] as Request;
    expect(replay.headers.get("Authorization")).toBe("Bearer A2");
  });

  it("drops the session when the refresh fails", async () => {
    setAccessToken("expired");
    fetchMock.mockResolvedValueOnce(json(401, {})).mockResolvedValueOnce(json(401, {}));
    const response = await authFetch("http://localhost/api/v1/tickets");
    expect(response.status).toBe(401);
    expect(getAccessToken()).toBeNull();
  });

  it("shares a single refresh between concurrent callers", async () => {
    fetchMock.mockResolvedValue(json(200, pair("A3")));
    const results = await Promise.all([refreshSession(), refreshSession(), refreshSession()]);
    expect(results).toEqual([true, true, true]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
