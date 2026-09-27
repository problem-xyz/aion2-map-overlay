/**
 * The slot table. The backend contract is frozen, so what this file pins is the wiring: every API
 * method reaches exactly one slot, with exactly the arguments Python declares, and every payload
 * that crosses the channel is stringified or parsed here and nowhere else. A method quietly wired
 * to the neighbouring slot, or one that drops an argument, is a bug that only shows up inside a
 * QWebEngineView with no console.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type BackendApi, type StepsApi, createBackendApi, createStepsApi } from "./api";
import type { BackendObject, QtSignal, RouteDoc, StepsObject } from "./contract";

/**
 * `call` is mocked so that a failure here names the wiring rather than the channel:
 * transport.test.ts owns the trailing-callback protocol, and this file owns which slot gets
 * called with what. It also keeps transport.ts, and the dev mock it can pull in behind
 * `import.meta.env.DEV`, out of this file's module graph.
 */
vi.mock("./transport", () => {
  const answer = (object: Record<string, unknown>, method: string, ...args: unknown[]) =>
    new Promise((resolve) => {
      const slot = object[method];
      if (typeof slot !== "function") throw new Error(`the double has no slot named ${method}`);
      (slot as (...a: unknown[]) => void).call(object, ...args, resolve);
    });
  return { call: vi.fn(answer) };
});

/** What each value-returning slot hands back. A test rewrites one entry and calls the API. */
interface Replies {
  state: string;
  save: string;
  editor: string;
  objects: string;
  steps: string;
}

function makeReplies(): Replies {
  return {
    state: '{"version":"2.0.0","running":true}',
    save: '{"ok":true,"id":"altgard-loop"}',
    editor: '{"seq":4,"id":"altgard-loop","doc":null}',
    objects: '[{"file":"altgard.json","mapName":"Altgard","categories":[],"nodes":[]}]',
    steps: '{"steps":[],"done":0,"title":"Altgard","size":"m","pinned":false,"opacity":0.9}',
  };
}

/** The signals are never touched by the API, but the double carries them so it is the same
 * surface the channel exposes: slots as plain functions, signals as connect/disconnect. */
function qtSignal(): QtSignal {
  return { connect: vi.fn(), disconnect: vi.fn() };
}

function makeBackendDouble(replies: Replies) {
  return {
    getState: vi.fn((cb: (json: string) => void) => cb(replies.state)),
    refreshRoutes: vi.fn(),

    start: vi.fn(),
    stop: vi.fn(),
    setPreview: vi.fn(),
    updateSettings: vi.fn(),
    resetSettings: vi.fn(),
    setOverlayVisible: vi.fn(),
    setCaptureVisible: vi.fn(),
    setPlayerAnchor: vi.fn(),

    selectRegion: vi.fn(),
    resetRegion: vi.fn(),

    setRoute: vi.fn(),
    deleteRoute: vi.fn(),
    reorderRoutes: vi.fn(),
    saveRoute: vi.fn((_payload: string, cb: (json: string) => void) => cb(replies.save)),
    exportRoute: vi.fn(),
    importRouteFile: vi.fn(),
    copyRouteCode: vi.fn(),
    pasteRouteCode: vi.fn(),

    setProgress: vi.fn(),
    resetProgress: vi.fn(),

    setStepsVisible: vi.fn(),
    setStepsPinned: vi.fn(),
    setStepsSize: vi.fn(),

    openEditor: vi.fn(),
    closeEditor: vi.fn(),
    getEditorRoute: vi.fn((cb: (json: string) => void) => cb(replies.editor)),

    getObjects: vi.fn((_mapId: string, cb: (json: string) => void) => cb(replies.objects)),

    openRoutesFolder: vi.fn(),
    openMapsFolder: vi.fn(),
    openLogsFolder: vi.fn(),
    openUrl: vi.fn(),
    copyText: vi.fn(),

    checkForUpdates: vi.fn(),
    downloadUpdate: vi.fn(),
    installUpdate: vi.fn(),
    skipUpdate: vi.fn(),

    stateChanged: qtSignal(),
    statsChanged: qtSignal(),
    previewChanged: qtSignal(),
    notify: qtSignal(),
    editorRequest: qtSignal(),
    progressChanged: qtSignal(),
    stepsChanged: qtSignal(),
    updateChanged: qtSignal(),
  } satisfies BackendObject;
}

function makeStepsDouble(replies: Replies) {
  return {
    getData: vi.fn((cb: (json: string) => void) => cb(replies.steps)),
    dragStart: vi.fn(),
    dragEnd: vi.fn(),
    action: vi.fn(),
    setHeight: vi.fn(),
    setHotspot: vi.fn(),
    dataChanged: qtSignal(),
  } satisfies StepsObject;
}

type BackendDouble = ReturnType<typeof makeBackendDouble>;
type StepsDouble = ReturnType<typeof makeStepsDouble>;

function firedSlots(double: object): string[] {
  return Object.entries(double)
    .filter(([, value]) => vi.isMockFunction(value) && value.mock.calls.length > 0)
    .map(([name]) => name);
}

/** Asserts that one call reached one slot, with exactly these arguments and nothing else fired. */
function expectOnlySlot(double: object, name: string, args: unknown[]) {
  expect(firedSlots(double)).toEqual([name]);
  expect((double as Record<string, unknown>)[name]).toHaveBeenCalledWith(...args);
}

/** safeParse writes to the console by design; a test that feeds it a bad payload says so here. */
function silenceErrors() {
  return vi.spyOn(console, "error").mockImplementation(() => {});
}

describe("createBackendApi", () => {
  let replies: Replies;
  let backend: BackendDouble;
  let api: BackendApi;

  beforeEach(() => {
    replies = makeReplies();
    backend = makeBackendDouble(replies);
    api = createBackendApi(backend);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const NO_ARGUMENT_METHODS = [
    "refreshRoutes",
    "start",
    "stop",
    "resetSettings",
    "selectRegion",
    "resetRegion",
    "importRouteFile",
    "pasteRouteCode",
    "resetProgress",
    "closeEditor",
    "openRoutesFolder",
    "openMapsFolder",
    "openLogsFolder",
    "checkForUpdates",
    "downloadUpdate",
  ] as const;

  it.each(NO_ARGUMENT_METHODS)("calls the %s slot, and no other", (name) => {
    api[name]();

    expectOnlySlot(backend, name, []);
  });

  const ARGUMENT_CALLS: Array<{
    label: string;
    run: (a: BackendApi) => void;
    slot: string;
    args: unknown[];
  }> = [
    { label: "setPreview", run: (a) => a.setPreview(true), slot: "setPreview", args: [true] },
    {
      label: "openUrl",
      run: (a) => a.openUrl("https://example.test/x"),
      slot: "openUrl",
      args: ["https://example.test/x"],
    },
    {
      label: "copyText",
      run: (a) => a.copyText("TEReugvvEFwP9qJ5eCwWasb9m7n2jpAoCi"),
      slot: "copyText",
      args: ["TEReugvvEFwP9qJ5eCwWasb9m7n2jpAoCi"],
    },
    {
      label: "setOverlayVisible",
      run: (a) => a.setOverlayVisible(false),
      slot: "setOverlayVisible",
      args: [false],
    },
    {
      label: "setCaptureVisible",
      run: (a) => a.setCaptureVisible(true),
      slot: "setCaptureVisible",
      args: [true],
    },
    {
      label: "setPlayerAnchor",
      run: (a) => a.setPlayerAnchor(0.5, 0.75),
      slot: "setPlayerAnchor",
      args: [0.5, 0.75],
    },
    {
      label: "setRoute",
      run: (a) => a.setRoute("altgard-loop"),
      slot: "setRoute",
      args: ["altgard-loop"],
    },
    {
      label: "deleteRoute",
      run: (a) => a.deleteRoute("altgard-loop"),
      slot: "deleteRoute",
      args: ["altgard-loop"],
    },
    {
      label: "reorderRoutes",
      run: (a) => a.reorderRoutes(["b", "a"]),
      slot: "reorderRoutes",
      args: ['["b","a"]'],
    },
    {
      label: "exportRoute",
      run: (a) => a.exportRoute("altgard-loop"),
      slot: "exportRoute",
      args: ["altgard-loop"],
    },
    {
      label: "copyRouteCode",
      run: (a) => a.copyRouteCode("altgard-loop"),
      slot: "copyRouteCode",
      args: ["altgard-loop"],
    },
    { label: "setProgress", run: (a) => a.setProgress(7), slot: "setProgress", args: [7] },
    {
      label: "setStepsVisible",
      run: (a) => a.setStepsVisible(true),
      slot: "setStepsVisible",
      args: [true],
    },
    {
      label: "setStepsPinned",
      run: (a) => a.setStepsPinned(false),
      slot: "setStepsPinned",
      args: [false],
    },
    { label: "setStepsSize", run: (a) => a.setStepsSize("l"), slot: "setStepsSize", args: ["l"] },
    {
      label: "openEditor",
      run: (a) => a.openEditor("altgard-loop"),
      slot: "openEditor",
      args: ["altgard-loop"],
    },
    {
      label: "installUpdate now",
      run: (a) => a.installUpdate(true),
      slot: "installUpdate",
      args: [true],
    },
    {
      label: "installUpdate on exit",
      run: (a) => a.installUpdate(false),
      slot: "installUpdate",
      args: [false],
    },
    {
      label: "skipUpdate",
      run: (a) => a.skipUpdate("1.2.0"),
      slot: "skipUpdate",
      args: ["1.2.0"],
    },
  ];

  it.each(ARGUMENT_CALLS)(
    "passes $label through to its own slot unchanged",
    ({ run, slot, args }) => {
      run(api);

      expectOnlySlot(backend, slot, args);
    },
  );

  it("sends a settings patch as JSON, and only the keys the caller changed", () => {
    api.updateSettings({ fps: 45, detector: "orb" });

    expectOnlySlot(backend, "updateSettings", ['{"fps":45,"detector":"orb"}']);
  });

  it("parses the state payload instead of handing the JSON string up", async () => {
    await expect(api.getState()).resolves.toEqual({ version: "2.0.0", running: true });
    expectOnlySlot(backend, "getState", [expect.any(Function)]);
  });

  it("reports no state at all when the state payload cannot be read", async () => {
    silenceErrors();
    replies.state = "{not json";

    await expect(api.getState()).resolves.toBeNull();
  });

  it("sends the route id and the document as one JSON payload, id included when it is null", () => {
    const doc = { format: "map-overlay-route", version: 1, name: "New" } as unknown as RouteDoc;

    void api.saveRoute(null, doc);

    expectOnlySlot(backend, "saveRoute", [JSON.stringify({ id: null, doc }), expect.any(Function)]);
  });

  it("sends the existing route id when the route is being overwritten", async () => {
    const doc = { format: "map-overlay-route", version: 1, name: "Altgard" } as unknown as RouteDoc;

    await expect(api.saveRoute("altgard-loop", doc)).resolves.toEqual({
      ok: true,
      id: "altgard-loop",
    });
    expect(backend.saveRoute).toHaveBeenCalledWith(
      JSON.stringify({ id: "altgard-loop", doc }),
      expect.any(Function),
    );
  });

  it("reports a failed save with a translatable code when the answer cannot be read", async () => {
    silenceErrors();
    replies.save = "";

    await expect(api.saveRoute(null, {} as RouteDoc)).resolves.toEqual({
      ok: false,
      code: "route.save_failed",
    });
  });

  it("parses the editor request envelope, not a bare document", async () => {
    await expect(api.getEditorRoute()).resolves.toEqual({
      seq: 4,
      id: "altgard-loop",
      doc: null,
    });
    expectOnlySlot(backend, "getEditorRoute", [expect.any(Function)]);
  });

  it("reports no editor request when its payload cannot be read", async () => {
    silenceErrors();
    replies.editor = "]";

    await expect(api.getEditorRoute()).resolves.toBeNull();
  });

  it("passes the map id to getObjects and parses the list back", async () => {
    await expect(api.getObjects("altgard")).resolves.toEqual([
      { file: "altgard.json", mapName: "Altgard", categories: [], nodes: [] },
    ]);
    expectOnlySlot(backend, "getObjects", ["altgard", expect.any(Function)]);
  });

  it("falls back to an empty list of object sets, so the editor has something to render", async () => {
    silenceErrors();
    replies.objects = "nope";

    await expect(api.getObjects("altgard")).resolves.toEqual([]);
  });
});

describe("createStepsApi", () => {
  let replies: Replies;
  let steps: StepsDouble;
  let api: StepsApi;

  beforeEach(() => {
    replies = makeReplies();
    steps = makeStepsDouble(replies);
    api = createStepsApi(steps);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("parses the plaque payload", async () => {
    await expect(api.getData()).resolves.toMatchObject({ title: "Altgard", size: "m", done: 0 });
    expectOnlySlot(steps, "getData", [expect.any(Function)]);
  });

  it("reports no plaque data when the payload cannot be read", async () => {
    silenceErrors();
    replies.steps = "{";

    await expect(api.getData()).resolves.toBeNull();
  });

  it("reports the start of a drag and its end through their own slots", () => {
    api.dragStart();
    expectOnlySlot(steps, "dragStart", []);

    vi.clearAllMocks();

    api.dragEnd();
    expectOnlySlot(steps, "dragEnd", []);
  });

  it("passes the name of the button that was pressed", () => {
    api.action("pin");

    expectOnlySlot(steps, "action", ["pin"]);
  });

  it("passes the measured height", () => {
    api.setHeight(240);

    expectOnlySlot(steps, "setHeight", [240]);
  });

  it("passes the hotspot as x, y, width, height, in that order", () => {
    api.setHotspot(10, 20, 300, 400);

    expectOnlySlot(steps, "setHotspot", [10, 20, 300, 400]);
  });
});
