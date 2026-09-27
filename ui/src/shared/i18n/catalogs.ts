/**
 * The locale files, loaded at build time and flattened to dotted keys.
 *
 * The same locales/*.json the Python side reads: one glob, no extraction step, no compiled
 * message format. Adding a language is adding a file -- the glob picks it up, `available` grows,
 * and the language selector sees it without another line of code.
 */

import { isPluralLeaf, type PluralForms } from "./plural";

export type Message = string | PluralForms;
export type Catalog = ReadonlyMap<string, Message>;

interface Branch {
  [key: string]: string | Branch | PluralForms;
}

// Eager: the catalogues are a few kilobytes and the app is a single inlined file, so there is
// nothing to gain from a second chunk and a loading state to render while it arrives.
const modules = import.meta.glob<Branch>("../../../../locales/*.json", {
  eager: true,
  import: "default",
});

function flatten(node: Branch, prefix: string, out: Map<string, Message>): void {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "object" && !isPluralLeaf(value)) {
      flatten(value, path, out);
    } else {
      out.set(path, value);
    }
  }
}

function build(): Map<string, Catalog> {
  const byLocale = new Map<string, Catalog>();
  for (const [path, tree] of Object.entries(modules)) {
    const name = path.split("/").pop();
    if (!name) continue;
    const flat = new Map<string, Message>();
    flatten(tree, "", flat);
    byLocale.set(name.replace(/\.json$/, ""), flat);
  }
  return byLocale;
}

export const catalogs: ReadonlyMap<string, Catalog> = build();

/** Which languages shipped, e.g. ["en", "ru"]. Sorted so the language selector is stable. */
export const available: readonly string[] = [...catalogs.keys()].sort();
