export interface SheenProps {
  /** ice for what is selected, gold for the one main action. */
  tone?: "ice" | "gold";
}

/**
 * The client's living surface, laid under a control's content: silk ribbons of light drifting
 * across it and a few motes coming and going, and on the ice tone a glint that runs along the
 * top and bottom glow lines every few seconds. Decoration only, hidden from assistive
 * technology; the host needs `position: relative`, `overflow: hidden` and `isolation: isolate`.
 *
 * Every layer moves by transform or opacity alone, which the compositor runs without a repaint:
 * the panel sits beside the game, and a surface that repainted each frame would cost it frames.
 * Under reduced motion the global rule stops every layer on its last, still frame.
 */
export default function Sheen({ tone = "ice" }: SheenProps) {
  return (
    <span className={`ui-sheen ui-sheen-${tone}`} aria-hidden="true">
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
