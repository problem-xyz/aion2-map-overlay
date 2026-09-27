import type { ReactNode } from "react";

export interface EditorEmptyProps {
  title?: ReactNode;
  muted?: boolean;
  children?: ReactNode;
}

/**
 * Placeholder in place of the map: no map, the map is still being cut into tiles, no connection.
 *
 * Deliberately context-free: one of those states is shown before the editor has built them.
 */
export default function EditorEmpty({
  title = null,
  muted = false,
  children = null,
}: EditorEmptyProps) {
  return (
    <div className={muted ? "editor-empty muted" : "editor-empty"}>
      {title ? <h2>{title}</h2> : null}
      {children}
    </div>
  );
}
