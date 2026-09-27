import { useEffect } from "react";

/** The editor window takes its title from the page, so this is not only cosmetic. */
export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    if (title) document.title = title;
  }, [title]);
}
