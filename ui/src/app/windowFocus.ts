/**
 * Marks the page's root while its window has the focus, so that looping decoration can stop
 * while the player is in the game.
 *
 * A running CSS animation makes Chromium composite a new frame at the display's rate, and Qt
 * WebEngine carries each one to the screen: measured on the idle panel, about a third of a CPU
 * core and a few percent of the GPU, next to the game, for a shimmer nobody is looking at.
 * Stylesheets read the mark as `:root[data-window-focused]`.
 */

export const FOCUS_ATTRIBUTE = "data-window-focused";

/** Keeps the mark in step with the window's focus. Returns the function that stops it. */
export function followWindowFocus(root: HTMLElement = document.documentElement): () => void {
  const sync = () => root.toggleAttribute(FOCUS_ATTRIBUTE, document.hasFocus());
  sync();
  window.addEventListener("focus", sync);
  window.addEventListener("blur", sync);
  return () => {
    window.removeEventListener("focus", sync);
    window.removeEventListener("blur", sync);
  };
}
