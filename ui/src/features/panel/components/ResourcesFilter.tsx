import { useEffect, useId, useRef, useState } from "react";

import { type MessageKey, useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import MarkIcon from "@/shared/ui/MarkIcon";
import { MAX_PICKED, RESOURCE_IDS, resourceIcon } from "@/shared/ui/resourceMarks";

export interface ResourcesFilterProps {
  /** The Resources switch: settings.show_resources. */
  on: boolean;
  /** The resources drawn while it is on: settings.resources, kept while it is off. */
  picked: readonly string[];
  /** The resources the list offers: those of the route's map, or of every map without one. */
  available: readonly string[];
  onToggle: (on: boolean) => void;
  onPick: (ids: string[]) => void;
}

/** A resource's name, as the game gives it: the key exists for every resource in the catalog. */
export function resourceName(t: (key: MessageKey) => string, id: string): string {
  return t(`common.resources.${id}` as MessageKey);
}

/**
 * The map's gathering points: a slot like the others in the filters row, which turns them on and
 * off, and beside it the list of the map's resources to tick the ones to draw. Ticking one turns
 * the switch on; turning the switch on with none ticked opens the list. The slot wears the mark
 * of the first resource ticked. No more than MAX_PICKED of the map's are ticked at once: past that
 * the rest wait, greyed, until one is unticked.
 */
export default function ResourcesFilter({
  on,
  picked,
  available,
  onToggle,
  onPick,
}: ResourcesFilterProps) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement | null>(null);
  const more = useRef<HTMLButtonElement | null>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
      more.current?.focus();
    };
    const onPointer = (e: PointerEvent) => {
      if (box.current && e.target instanceof Node && !box.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("pointerdown", onPointer, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("pointerdown", onPointer, true);
    };
  }, [open]);

  const shown = picked.find((id) => available.includes(id)) ?? available[0] ?? RESOURCE_IDS[0];
  const full = picked.filter((id) => available.includes(id)).length >= MAX_PICKED;

  const pick = (id: string, checked: boolean) => {
    const next = new Set(picked);
    if (checked) next.add(id);
    else next.delete(id);
    // in the catalog's order, whatever order they were ticked in; one no map has is dropped
    onPick(RESOURCE_IDS.filter((r) => next.has(r)));
    if (checked && !on) onToggle(true);
  };

  return (
    <div className="pn-chip-group" ref={box}>
      <label className="pn-chip" title={t("panel.filters.resources")}>
        <input
          type="checkbox"
          checked={on}
          onChange={(e) => {
            onToggle(e.target.checked);
            if (e.target.checked && !picked.some((id) => available.includes(id))) setOpen(true);
          }}
          aria-label={t("panel.filters.resources")}
        />
        {shown ? <MarkIcon name={resourceIcon(shown)} className="pn-chip-icon" /> : null}
        <span className="pn-chip-label" aria-hidden="true">
          {t("panel.filters.resourcesShort")}
        </span>
      </label>
      <button
        ref={more}
        type="button"
        className="pn-chip-more"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={t("panel.filters.resourcesPick")}
        title={t("panel.filters.resourcesPick")}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon name="chevronDown" />
      </button>
      {open ? (
        <div
          id={listId}
          role="group"
          aria-label={t("panel.filters.resourcesPick")}
          className="ui-frame pn-resources"
        >
          {available.length === 0 ? (
            <p className="pn-resources-none">{t("panel.filters.resourcesNone")}</p>
          ) : (
            available.map((id) => (
              <label key={id} className="pn-resource">
                <input
                  type="checkbox"
                  checked={picked.includes(id)}
                  disabled={full && !picked.includes(id)}
                  onChange={(e) => pick(id, e.target.checked)}
                />
                <MarkIcon name={resourceIcon(id)} className="pn-resource-icon" />
                <span className="pn-resource-name">{resourceName(t, id)}</span>
              </label>
            ))
          )}
          {full ? (
            <p className="pn-resources-none">
              {t("panel.filters.resourcesMax", { count: MAX_PICKED })}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
