/**
 * Getting hold of the Python object, or a mock of it.
 *
 * `window.qt.webChannelTransport` only exists inside a QWebEngineView, so opening the built
 * page in a normal browser has to fail in a way the UI can show rather than throwing into a
 * console nobody is watching. In dev it falls back to the mock instead, which is what makes
 * `?mock=1` in a browser possible at all.
 */

export class BackendError extends Error {
  readonly code: string;

  constructor(code: string, message?: string) {
    super(message ?? code);
    this.name = "BackendError";
    this.code = code;
  }
}

interface QWebChannelObjects {
  objects: Record<string, unknown>;
}

declare global {
  interface Window {
    qt?: { webChannelTransport?: unknown };
    /**
     * Qt's own qwebchannel.js, which Python injects into every page before the page's scripts
     * run. It is not bundled: kept inside the Qt libraries, it is replaced along with them.
     */
    QWebChannel?: new (
      transport: unknown,
      onReady: (channel: QWebChannelObjects) => void,
    ) => unknown;
    __mock?: unknown;
  }
}

/**
 * Asked for the mock, or there is no Qt to talk to. Only consulted in a dev build.
 *
 * The parameter's value decides, not its presence: inside a dev build of the app `?mock=0`
 * means "talk to the real backend", and reading the presence alone made it mean the opposite.
 */
function askedForMock(): boolean {
  return new URLSearchParams(window.location.search).get("mock") === "1" || !window.qt;
}

/**
 * Connect to a named Python object: "backend" for the panel and the editor, "steps" for the
 * plaque.
 */
export async function connectObject<T>(name: string): Promise<T> {
  // import.meta.env.DEV has to be inline here, not behind a helper: the bundler replaces it
  // with a literal and only then can it fold the branch away and drop the mock chunk. Hiding
  // it inside a function call shipped the whole mock in the production bundle.
  if (import.meta.env.DEV && askedForMock()) {
    const mod = await import("@/dev/mockBackend");
    return mod.createMockObject(name) as T;
  }

  const transport = window.qt?.webChannelTransport;
  if (!transport) {
    throw new BackendError("backend.noTransport");
  }

  const QWebChannel = window.QWebChannel;
  return new Promise<T>((resolve, reject) => {
    try {
      if (!QWebChannel) {
        throw new Error("qwebchannel.js was not injected into the page");
      }
      new QWebChannel(transport, (channel) => {
        const object = channel.objects[name];
        if (!object) {
          reject(new BackendError("backend.noObject", name));
          return;
        }
        resolve(object as T);
      });
    } catch (e) {
      reject(new BackendError("backend.channelFailed", String(e)));
    }
  });
}

/**
 * How long a slot may take before the call is written off as lost.
 *
 * Not a deadline anyone should reach: every slot reached through `call` is ordinary work on
 * Python's main thread -- a JSON dump, one file read, one atomic write -- and answers in
 * milliseconds. The margin is for a main thread busy elsewhere, which on this app means
 * seconds and not fractions of one: building tiles for a freshly imported map, or feature
 * detection over a large map reference. Past that a slot is not slow, it is gone, and saying
 * so beats a window that waits for the rest of the session.
 */
export const CALL_TIMEOUT_MS = 15_000;

/**
 * Promisify a slot that returns a value. QWebChannel hands results back through a trailing
 * callback, so every such call looks like this.
 */
export function call<T>(object: unknown, method: string, ...args: unknown[]): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const fn = (object as Record<string, unknown>)?.[method];
    if (typeof fn !== "function") {
      reject(new BackendError("backend.noSlot", method));
      return;
    }

    const timer = setTimeout(
      () => reject(new BackendError("backend.slotTimeout", method)),
      CALL_TIMEOUT_MS,
    );

    try {
      (fn as (...a: unknown[]) => void).call(object, ...args, (value: T) => {
        clearTimeout(timer);
        resolve(value);
      });
    } catch (e) {
      clearTimeout(timer);
      throw e; // the executor turns this into a rejection, as it did before there was a timer
    }
  });
}
