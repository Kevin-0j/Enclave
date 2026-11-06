import { resolveSessionUrl } from "./player";

describe("resolveSessionUrl", () => {
  const whep = "/media/t/aaa/c/bbb/sub/whep";
  it("keeps the /media prefix for MediaMTX root-relative locations", () => {
    expect(resolveSessionUrl(whep, "/t/aaa/c/bbb/sub/whep/1234")).toBe(`${window.location.origin}/media/t/aaa/c/bbb/sub/whep/1234`);
  });
  it("accepts absolute locations from remote media nodes", () => {
    expect(resolveSessionUrl(whep, "https://node-2.example/t/x/whep/9")).toBe("https://node-2.example/t/x/whep/9");
  });
  it("returns null without a location", () => {
    expect(resolveSessionUrl(whep, null)).toBeNull();
  });
});
