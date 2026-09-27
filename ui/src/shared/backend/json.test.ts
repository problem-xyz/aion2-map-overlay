/**
 * The parse boundary. What matters here is not that JSON.parse works, but that a payload from
 * Python can never throw into a render: anything unreadable has to come back as the caller's own
 * fallback, and the console line must stay short enough that one bad frame of stats does not
 * bury the log.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { safeParse } from "./json";

/** Silences the module's own console.error and hands the spy over for assertions. */
function silenceErrors() {
  return vi.spyOn(console, "error").mockImplementation(() => {});
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("safeParse", () => {
  it("parses an object payload", () => {
    expect(safeParse('{"running":true,"route":"altgard"}', null)).toEqual({
      running: true,
      route: "altgard",
    });
  });

  it("parses arrays and bare primitives, not only objects", () => {
    expect(safeParse("[1,2,3]", [])).toEqual([1, 2, 3]);
    expect(safeParse("42", 0)).toBe(42);
    expect(safeParse('"altgard"', "")).toBe("altgard");
    expect(safeParse("false", true)).toBe(false);
  });

  it("returns the fallback for an empty string, null and undefined", () => {
    const fallback = { ok: false };

    expect(safeParse("", fallback)).toBe(fallback);
    expect(safeParse(null, fallback)).toBe(fallback);
    expect(safeParse(undefined, fallback)).toBe(fallback);
  });

  it("returns the fallback for a payload that is not a string at all", () => {
    // Qt hands a slot's result back untyped, so a slot that forgot to stringify arrives here as
    // an object. The cast stands for that: the declared type says it cannot happen, Python can.
    const notAString = { running: true } as unknown as string;

    expect(safeParse(notAString, null)).toBeNull();
  });

  it("returns the fallback instead of throwing when the payload is not JSON", () => {
    const errors = silenceErrors();
    const fallback = { ok: false };

    expect(() => safeParse("{oops", fallback)).not.toThrow();
    expect(safeParse("{oops", fallback)).toBe(fallback);
    expect(errors).toHaveBeenCalled();
  });

  it("returns the fallback for a whitespace-only payload, which is not valid JSON", () => {
    silenceErrors();

    expect(safeParse("   ", null)).toBeNull();
  });

  it("hands back the very object it was given as the fallback, for comparison by identity", () => {
    silenceErrors();
    const fallback: string[] = [];

    expect(safeParse("not json", fallback)).toBe(fallback);
  });

  it("parses the literal null payload as null rather than treating it as missing", () => {
    // Python sends "null" for "no editor route yet", which is a real answer and not a failure;
    // falling back here would hide the difference between an answer and a broken channel.
    const errors = silenceErrors();

    expect(safeParse("null", { ok: false })).toBeNull();
    expect(errors).not.toHaveBeenCalled();
  });

  it("logs at most the first 200 characters of an unparseable payload", () => {
    const errors = silenceErrors();
    const huge = `{${"x".repeat(5000)}`;

    safeParse(huge, null);

    const logged = errors.mock.calls[0]?.[2] as string | undefined;
    expect(typeof logged).toBe("string");
    expect(logged).toHaveLength(200);
  });

  it("says nothing on the console when the payload parses", () => {
    const errors = silenceErrors();

    safeParse('{"ok":true}', null);

    expect(errors).not.toHaveBeenCalled();
  });
});
