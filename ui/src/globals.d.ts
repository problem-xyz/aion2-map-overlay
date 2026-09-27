/**
 * Declarations that belong to no single module.
 *
 * `checkJs` is on for the remaining `.jsx` files, so the two places where this UI steps outside
 * what React's own types describe have to be written down somewhere.
 */

import "react";

declare module "react" {
  /**
   * CSS custom properties in a `style` prop. The panel drives plain CSS through them
   * (`--num-color`, `--so-scale`, `--so-alpha`) instead of writing computed values into
   * every rule, and React's own `CSSProperties` rejects any key it does not know.
   */
  interface CSSProperties {
    [key: `--${string}`]: string | number | undefined;
  }
}

declare global {
  interface Window {
    /**
     * Set by the editor page. The Python window asks the page to confirm before closing,
     * because only the page knows whether there are unsaved changes. `true` means the page has
     * taken it over: it has closed the window, or is asking the user.
     */
    __requestClose?: () => boolean;
  }
}
