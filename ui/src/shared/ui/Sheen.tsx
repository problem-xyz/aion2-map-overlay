export interface SheenProps {
  /** ice for what is selected, gold for the one main action. */
  tone?: "ice" | "gold";
  /** The glow lines and the ribbons standing, with nothing running: for a surface over the game. */
  still?: boolean;
}

/**
 * The client's living surface, laid under a control's content: silk ribbons of light drifting
 * across it and a few motes coming and going, and on the ice tone a glint that runs along the
 * top and bottom glow lines every few seconds. Decoration only, hidden from assistive
 * technology; the host needs `position: relative`, `overflow: hidden` and `isolation: isolate`.
 *
 * Every layer moves by transform or opacity alone, so nothing repaints, but each frame is still
 * composited and carried to the screen: about a third of a CPU core on the idle panel. The
 * layers therefore stand while their window is out of focus (`app/windowFocus.ts`), and under
 * reduced motion the global rule stops every layer on its last, still frame.
 */
export default function Sheen({ tone = "ice", still = false }: SheenProps) {
  return (
    <span
      className={`ui-sheen ui-sheen-${tone}${still ? " ui-sheen-still" : ""}`}
      aria-hidden="true"
    >
      <span className="ui-sheen-silk" />
      <span className="ui-sheen-motes" />
      <span className="ui-sheen-motes ui-sheen-late" />
      {tone === "ice" ? (
        <>
          <span className="ui-sheen-glint ui-sheen-top" />
          <span className="ui-sheen-glint ui-sheen-bottom" />
        </>
      ) : null}
    </span>
  );
}
