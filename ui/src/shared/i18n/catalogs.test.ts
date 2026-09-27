import ts from "typescript";
import { describe, expect, it } from "vitest";

import { available, catalogs, type Message } from "./catalogs";

const PLACEHOLDER = /\{(\w+)\}/g;
const CYRILLIC = /[\u0400-\u04FF]/;

// Read through Vite rather than node:fs: the suite runs in jsdom, and this keeps the test free
// of @types/node for the sake of two file reads.
const englishRaw = Object.values(
  import.meta.glob<string>("../../../../locales/en.json", {
    eager: true,
    query: "?raw",
    import: "default",
  }),
)[0];

const sources = import.meta.glob<string>("../../**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
});

function placeholders(message: Message): Set<string> {
  const forms = typeof message === "string" ? [message] : Object.values(message);
  const names = new Set<string>();
  for (const form of forms) {
    for (const match of form.matchAll(PLACEHOLDER)) {
      const name = match[1];
      if (name) names.add(name);
    }
  }
  return names;
}

const en = catalogs.get("en");
if (!en) throw new Error("locales/en.json did not load");

describe("locale catalogues", () => {
  it("ship more than one language", () => {
    expect(available.length).toBeGreaterThan(1);
    expect(available).toContain("en");
  });

  it("all have exactly the key set of English", () => {
    for (const locale of available) {
      const catalog = catalogs.get(locale);
      expect(catalog, locale).toBeDefined();
      expect([...catalog!.keys()].sort(), locale).toEqual([...en.keys()].sort());
    }
  });

  it("give every plural leaf the categories its language actually uses", () => {
    for (const locale of available) {
      // Ask the platform rather than hard-coding: this is what makes a new language just a file.
      const expected = [...new Intl.PluralRules(locale).resolvedOptions().pluralCategories].sort();
      for (const [key, message] of catalogs.get(locale)!) {
        if (typeof message === "string") continue;
        expect(Object.keys(message).sort(), `${locale} ${key}`).toEqual(expected);
      }
    }
  });

  it("use the same placeholders in every language", () => {
    for (const locale of available) {
      for (const [key, message] of catalogs.get(locale)!) {
        const reference = en.get(key);
        expect(reference, `${locale} ${key}`).toBeDefined();
        expect([...placeholders(message)].sort(), `${locale} ${key}`).toEqual(
          [...placeholders(reference!)].sort(),
        );
      }
    }
  });

  it("keep Cyrillic out of the English catalogue", () => {
    expect(englishRaw).toBeTruthy();
    expect(CYRILLIC.test(englishRaw ?? "")).toBe(false);
  });
});

describe("keys used by the UI", () => {
  // Parsed, not grepped: a t("...") inside a comment is not a call site, and a regex cannot tell
  // the difference -- keys.ts documents its own type with a deliberate typo in a doc comment.
  const used = new Set<string>();
  // Keys also reach t() through a MessageKey constant or a ternary, which the call-site scan
  // cannot see. For the "is anything orphaned" report, any string literal that is a key counts.
  const mentioned = new Set<string>();
  for (const [file, text] of Object.entries(sources)) {
    if (file.includes(".test.")) continue;
    const sf = ts.createSourceFile(
      file,
      text,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    const visit = (node: ts.Node): void => {
      if (ts.isCallExpression(node)) {
        const callee = node.expression;
        const name = ts.isIdentifier(callee)
          ? callee.text
          : ts.isPropertyAccessExpression(callee)
            ? callee.name.text
            : "";
        const first = node.arguments[0];
        if (name === "t" && first && ts.isStringLiteralLike(first)) used.add(first.text);
      }
      if (ts.isStringLiteralLike(node)) mentioned.add(node.text);
      ts.forEachChild(node, visit);
    };
    visit(sf);
  }

  it("all exist in the English catalogue", () => {
    const missing = [...used].filter((key) => !en.has(key));
    expect(missing).toEqual([]);
  });

  it("are reported when a catalogue key has no caller", () => {
    // Not a failure: notify.* and native.* are called from Python, not from here.
    const unused = [...en.keys()].filter(
      (key) => !mentioned.has(key) && !key.startsWith("notify.") && !key.startsWith("native."),
    );
    // Naming them matters: some are reached dynamically (BackendGate builds
    // `common.${error.code}`), so "no literal" is not the same as "dead".
    if (unused.length) console.info(`[i18n] no literal caller: ${unused.join(", ")}`);
    expect(Array.isArray(unused)).toBe(true);
  });
});
