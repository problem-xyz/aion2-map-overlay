// The shared styles first, then the panel's, which the other pages borrow classes from: a
// feature's own stylesheet comes after both and can override them. Each feature stylesheet used
// to @import base.css itself, and the copy that landed last overrode the editor's own rules.
import "@/shared/styles/base.css";
import "@/features/panel/panel.css";

import React from "react";
import { createRoot } from "react-dom/client";

import { AppShell } from "@/app/AppShell";
import { PAGES, pageFromHash } from "@/app/pages";
import { followWindowFocus } from "@/app/windowFocus";
import { BackendGate } from "@/shared/backend/BackendGate";
import { BackendProvider } from "@/shared/backend/BackendProvider";
import { I18nProvider } from "@/shared/i18n";

const page = pageFromHash(window.location.hash);
const Page = PAGES[page];
const isSteps = page === "steps";

// The plaque lives in a transparent window: a dark page background would paint over the game.
if (isSteps) document.documentElement.classList.add("steps-page");

followWindowFocus();

// The plaque talks to a different Qt object, with its own state signal and getter.
const connection = isSteps
  ? { object: "steps", stateSignal: "dataChanged", stateGetter: "getData" }
  : { object: "backend", stateSignal: "stateChanged", stateGetter: "getState" };

const container = document.getElementById("root");
if (!container) throw new Error("index.html has no #root to mount into");

createRoot(container).render(
  <React.StrictMode>
    {/* Above BackendProvider on purpose: the connection screens are the first thing a user can
        see, and they have to be translated as well. */}
    <I18nProvider>
      <BackendProvider {...connection}>
        <BackendGate quiet={isSteps}>
          {isSteps ? (
            <Page />
          ) : (
            <AppShell>
              <Page />
            </AppShell>
          )}
        </BackendGate>
      </BackendProvider>
    </I18nProvider>
  </React.StrictMode>,
);
