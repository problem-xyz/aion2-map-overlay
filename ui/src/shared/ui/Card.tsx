import { useId, type ReactNode } from "react";

export interface CardProps {
  title: ReactNode;
  /** The heading's id, for a control in the head that the heading names; made up if absent. */
  headingId?: string;
  /** At the end of the head's line: the card's switch, or its one action. */
  aside?: ReactNode;
  children?: ReactNode;
}

/**
 * One group of a section, framed as the editor's inspector is: the warm hairline, a title with
 * its switch or button on the same line, the ice rule under it, then the rows. The rows are the
 * card's direct children, and the card draws the hairline between them.
 */
export default function Card({ title, headingId, aside = null, children = null }: CardProps) {
  const ownId = useId();
  const id = headingId ?? ownId;
  return (
    <section className="ui-frame pn-card" aria-labelledby={id}>
      <div className="pn-card-head">
        <h2 id={id}>{title}</h2>
        {aside}
      </div>
      <div className="pn-card-rule" />
      <div className="pn-card-body">{children}</div>
    </section>
  );
}
