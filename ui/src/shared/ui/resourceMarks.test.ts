/**
 * The gathering resources' marks, read out of assets/marks/resources.json -- the file the overlay
 * draws them by as well. Every resource has to come out drawable and named in every language.
 */

import { describe, expect, it } from "vitest";

import { catalogs } from "@/shared/i18n";

import { iconLayers } from "./markIcons";
import {
  RESOURCE_IDS,
  isResourceIcon,
  resourceColor,
  resourceIcon,
  resourceLayers,
  resourceOf,
} from "./resourceMarks";

describe("resource marks", () => {
  it("are named after the category, gathering-<id>", () => {
    expect(resourceOf("gathering-odyle")).toBe("odyle");
    expect(resourceOf("gathering")).toBeNull();
    expect(resourceOf("gathering-")).toBeNull();
    expect(resourceIcon("ruby")).toBe("gathering-ruby");
    expect(isResourceIcon("cube")).toBe(false);
  });

  it("draw every resource in its own colours, no role left unfilled", () => {
    expect(RESOURCE_IDS.length).toBeGreaterThan(0);
    for (const id of RESOURCE_IDS) {
      const layers = resourceLayers(resourceIcon(id));
      expect(layers.length, id).toBeGreaterThan(0);
      for (const layer of layers) {
        for (const paint of [layer.fill, layer.stroke]) {
          if (paint !== undefined) expect(paint, id).toMatch(/^#[0-9a-f]{6}$/i);
        }
      }
      expect(resourceColor(resourceIcon(id)), id).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("are what iconLayers hands the map and the lists", () => {
    expect(iconLayers("gathering-ruby")).toBe(resourceLayers("gathering-ruby"));
    expect(iconLayers("gathering-none")).toEqual([]);
  });

  it("each have a name in every language", () => {
    for (const [lang, catalog] of catalogs) {
      for (const id of RESOURCE_IDS) {
        expect(typeof catalog.get(`common.resources.${id}`), `${lang}: ${id}`).toBe("string");
      }
    }
  });
});
