import {
  type CSSProperties,
  type PointerEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { StepEntry, StepsData, StepsSize } from "@/shared/backend/contract";
import { useStepsApi } from "@/shared/backend/hooks";
import { useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import MarkIcon from "@/shared/ui/MarkIcon";
import { type MarkIconName, questIcon } from "@/shared/ui/markIcons";
import Sheen from "@/shared/ui/Sheen";

import { type RowFit, fitRows } from "./fitRows";
import "./steps.css";

// The three old steps as scales, for a backend from before api 11 that sends no scale
const SIZE_SCALE: Record<StepsSize, number> = { s: 0.85, m: 1, l: 1.25 };
// The plaque shows as many rows as the height the user gave it holds, and says how many points
// are left beyond them. The steps passed take their rows first, one line each, but give way
// before fewer than MIN_AHEAD steps ahead are left. MAX_ROWS only bounds what is measured.
const MAX_ROWS = 30;
const MIN_AHEAD = 3;
const GRIP = 8; // the resize strips, for a backend from before api 18 that sends no width
const HOTSPOT_PAD = 6; // slack around the unpin button, so the cursor is caught more reliably

/** Hotspot rectangle in the order `setHotspot` expects: x, y, width, height. */
type Hotspot = [number, number, number, number];

/** A step's icon, as the editor's and the panel's lists draw it: its quest star first. */
function stepIcon(s: StepEntry): MarkIconName | null {
  if (s.icon) return questIcon(s.icon);
  return s.object ?? null;
}

/**
 * The steps plaque over the game (the window from steps_window.py), drawn as the panel's
 * cards are: the warm hairline, a title with its counter and buttons over the ice rule, and
 * the points as the editor lists them -- number, icon, label -- the next one in the band of a
 * selected row.
 *
 * The window is native: Python moves and sizes it. The page only reports "drag started" and
 * "released", and draws the resize cursors over the strips along the right and bottom edges,
 * where Python takes a press for itself. The card fills the window, and its list shows as many
 * rows as fit: every row that could be shown is laid out once more, unseen, to be measured.
 */
export default function StepsPage() {
  const bridge = useStepsApi();
  // this page is connected to the `steps` object, so the store holds StepsData, not AppState
  const data = useBackendState<StepsData, StepsData | null>((s) => s);
  const { t, setLanguage } = useI18n();
  const card = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const measure = useRef<HTMLUListElement>(null);
  const sentHotspot = useRef("");
  const [fit, setFit] = useState<RowFit | null>(null);

  // The plaque talks to the `steps` object and never sees getState, so the language reaches it in
  // its own payload: Python has already resolved `auto` there. The panel and the editor get the
  // same thing from LanguageSync.
  const language = data?.language;
  useEffect(() => {
    if (language) setLanguage(language);
  }, [language, setLanguage]);

  useLayoutEffect(() => {
    const node = card.current;
    if (!node || !bridge) return undefined;
    const report = () => {
      // a pinned window is click-through as a whole, so Python is told where the buttons that
      // stay live -- the step arrows and the pin, side by side -- sit: over that one rectangle
      // the window starts catching the mouse again. IconButton is a plain function component
      // under React 18 and cannot take a ref, so the group is found inside the card that is
      // being measured anyway.
      const group = node.querySelector(".so-live");
      const box = group ? group.getBoundingClientRect() : null;
      const rect: Hotspot = box
        ? [
            Math.floor(box.left) - HOTSPOT_PAD,
            Math.floor(box.top) - HOTSPOT_PAD,
            Math.ceil(box.width) + 2 * HOTSPOT_PAD,
            Math.ceil(box.height) + 2 * HOTSPOT_PAD,
          ]
        : [0, 0, 0, 0];
      const key = rect.join(",");
      if (key !== sentHotspot.current) {
        sentHotspot.current = key;
        bridge.setHotspot(rect[0], rect[1], rect[2], rect[3]);
      }
    };
    report();
    const observer = new ResizeObserver(report);
    observer.observe(node);
    return () => observer.disconnect();
  }, [bridge, data]);

  // Which rows fit, from the unseen copy of them all. The visible list takes the height the card
  // leaves it whatever it holds, and the copy is out of the flow, so what is shown never changes
  // what is measured and the observer cannot loop.
  useLayoutEffect(() => {
    const room = list.current;
    const copy = measure.current;
    if (!room || !copy) return undefined;
    const update = () => {
      const heights = (selector: string) =>
        [...copy.querySelectorAll(selector)].map((row) => row.getBoundingClientRect().height);
      const style = getComputedStyle(room);
      const next = fitRows({
        behind: heights(".passed"),
        ahead: heights(".ahead"),
        left: Number(copy.dataset.left ?? 0),
        more: heights(".so-more")[0] ?? 0,
        room:
          room.clientHeight -
          (parseFloat(style.paddingTop) || 0) -
          (parseFloat(style.paddingBottom) || 0),
        minAhead: MIN_AHEAD,
      });
      setFit((last) =>
        last && last.behind === next.behind && last.ahead === next.ahead ? last : next,
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(room);
    observer.observe(copy);
    return () => observer.disconnect();
  }, [data]);

  const startDrag = useCallback(
    (e: PointerEvent<HTMLDivElement>) => {
      // e.target is typed EventTarget, but a pointerdown inside the card always comes from
      // an element
      if (
        !bridge ||
        e.button !== 0 ||
        data?.pinned ||
        (e.target as Element).closest(".so-btn, .so-grip")
      )
        return;
      e.preventDefault();
      bridge.dragStart();
      const stop = () => {
        bridge.dragEnd();
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
      };
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    },
    [bridge, data?.pinned],
  );

  if (!data) return null;
  const rest = data.steps.filter((s) => s.n > data.done);
  const first = rest[0];
  if (!first) return null;

  const total = data.steps.length;
  const next = first.n;
  // the last steps passed, as many as the map keeps faded behind you (route_past)
  const passed = data.steps.filter((s) => s.n <= data.done);
  const behindAll = passed.slice(passed.length - Math.min(data.past ?? 0, passed.length));
  // every point on a line of its own, labelled or not: the unlabelled ones used to run together
  // as a ribbon of dots, which read as one step (owner)
  const aheadAll = rest.slice(0, MAX_ROWS);
  const behind = fit
    ? behindAll.slice(behindAll.length - Math.min(fit.behind, behindAll.length))
    : behindAll;
  const ahead = fit ? aheadAll.slice(0, Math.max(1, fit.ahead)) : aheadAll;
  const beyond = rest.length - ahead.length;
  const scale = data.scale ?? SIZE_SCALE[data.size] ?? 1;
  const style: CSSProperties = {
    "--so-scale": scale,
    "--so-alpha": data.opacity,
    "--so-grip": `${data.grip ?? GRIP}px`,
  };

  const dot = (s: StepEntry) => {
    // the dot colour comes from the route data, so it travels in a CSS variable and the
    // .so-num rule in steps.css does the painting
    const dotStyle: CSSProperties = { "--so-num-color": s.color };
    return (
      <span className={`so-num ${s.n === next ? "next" : ""}`} style={dotStyle}>
        {s.n}
      </span>
    );
  };
  const icon = (s: StepEntry) => {
    const name = stepIcon(s);
    return name ? <MarkIcon name={name} className="so-icon" /> : null;
  };

  return (
    <div
      ref={card}
      className={`so-card ${data.pinned ? "pinned" : "loose"}`}
      style={style}
      onPointerDown={startDrag}
    >
      <div className="so-head">
        {/* the title attribute: a long name ends in an ellipsis, and the loose plaque can be hovered */}
        <span className="so-title" title={data.title}>
          {data.title}
        </span>
        {/* "3 / 12" is read out as two numbers and a slash, so the counter carries a sentence.
            The role is what makes that name count: a bare span is `generic`, and a name on a
            generic element is one browsers are required to ignore. */}
        <span
          className="so-count"
          role="img"
          aria-label={t("steps.counter", { done: data.done, count: total })}
        >
          <b>{data.done}</b> / {total}
        </span>
        <div className="so-actions">
          {/* the buttons a pinned plaque keeps: one rectangle for the window's hotspot */}
          <div className="so-live">
            {/* a step back and a step forward, while progress counts: a point skipped on
                purpose, or one ticked off by walking past it, is put right from here */}
            {data.switch ? (
              <>
                <IconButton
                  className="so-btn"
                  label={t("steps.stepBack")}
                  icon={<Icon name="chevronLeft" />}
                  disabled={data.done === 0}
                  onClick={() => bridge?.action("prev")}
                />
                <IconButton
                  className="so-btn"
                  label={t("steps.stepNext")}
                  icon={<Icon name="chevron" />}
                  onClick={() => bridge?.action("next")}
                />
              </>
            ) : null}
            <IconButton
              className={`so-btn so-pin ${data.pinned ? "on" : ""}`}
              label={data.pinned ? t("steps.unpin") : t("steps.pin")}
              icon={<Icon name={data.pinned ? "pinOn" : "pin"} />}
              onClick={() => bridge?.action("pin")}
            />
          </div>
          {data.pinned ? null : (
            <IconButton
              className="so-btn so-close"
              label={t("steps.hide")}
              icon={<Icon name="closeGlint" />}
              onClick={() => bridge?.action("close")}
            />
          )}
        </div>
      </div>
      <div className="so-rule" />

      <ul ref={list} className="so-list">
        {behind.map((s) => (
          <li key={s.n} className="so-row passed">
            {dot(s)}
            {icon(s)}
            {s.text ? <span className="so-text">{s.text}</span> : null}
          </li>
        ))}
        {ahead.map((s) => (
          <li
            key={s.n}
            className={s.n === next ? "so-row next" : "so-row"}
            aria-current={s.n === next ? "step" : undefined}
          >
            {/* the current step lives, as the selected tile of the panel's menu does */}
            {s.n === next ? <Sheen /> : null}
            {dot(s)}
            {icon(s)}
            {s.text ? <span className="so-text">{s.text}</span> : null}
          </li>
        ))}
        {beyond > 0 ? (
          <li className="so-row so-more">{t("steps.more", { count: beyond })}</li>
        ) : null}
      </ul>

      {/* every row that could be shown, laid out at the list's width and never seen */}
      <ul ref={measure} className="so-list so-measure" aria-hidden="true" data-left={rest.length}>
        {behindAll.map((s) => (
          <li key={s.n} className="so-row passed">
            {dot(s)}
            {icon(s)}
            {s.text ? <span className="so-text">{s.text}</span> : null}
          </li>
        ))}
        {aheadAll.map((s) => (
          <li key={s.n} className={s.n === next ? "so-row ahead next" : "so-row ahead"}>
            {dot(s)}
            {icon(s)}
            {s.text ? <span className="so-text">{s.text}</span> : null}
          </li>
        ))}
        <li className="so-row so-more">{t("steps.more", { count: rest.length })}</li>
      </ul>

      {/* Where a press sizes the loose plaque. Python takes the press before the page sees it;
          these only show the cursor that says so. */}
      {data.pinned ? null : (
        <>
          <div className="so-grip so-grip-r" />
          <div className="so-grip so-grip-b" />
          <div className="so-grip so-grip-rb" />
        </>
      )}
    </div>
  );
}
