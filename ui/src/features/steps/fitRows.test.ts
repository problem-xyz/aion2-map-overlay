/**
 * How many of the checklist's rows fit the height the user dragged it to: whole rows only, the
 * "N more" line under them whenever a step ahead is left out, and the steps passed giving way
 * before the steps ahead fall below the minimum.
 */

import { describe, expect, it } from "vitest";

import { fitRows } from "./fitRows";

const rows = (count: number, height = 30) => Array.from({ length: count }, () => height);

describe("fitRows", () => {
  it("shows every row while nothing has been laid out", () => {
    expect(
      fitRows({ behind: rows(2), ahead: rows(5), left: 5, more: 20, room: 0, minAhead: 3 }),
    ).toEqual({ behind: 2, ahead: 5 });
  });

  it("shows whole rows only, and leaves room for the line saying how many are left", () => {
    // 100 px: three rows would fit, but then the line under them would not
    expect(
      fitRows({ behind: [], ahead: rows(10), left: 10, more: 20, room: 100, minAhead: 3 }),
    ).toEqual({ behind: 0, ahead: 2 });
  });

  it("needs no such line once the last step fits", () => {
    expect(
      fitRows({ behind: [], ahead: rows(3), left: 3, more: 20, room: 90, minAhead: 3 }),
    ).toEqual({ behind: 0, ahead: 3 });
  });

  it("keeps the line for a long route whose rows were not all measured", () => {
    expect(
      fitRows({ behind: [], ahead: rows(3), left: 40, more: 20, room: 90, minAhead: 3 }),
    ).toEqual({ behind: 0, ahead: 2 });
  });

  it("drops the oldest steps passed before fewer than the minimum ahead are shown", () => {
    // room for five rows and the line: three passed would leave two ahead
    expect(
      fitRows({ behind: rows(3), ahead: rows(10), left: 10, more: 30, room: 180, minAhead: 3 }),
    ).toEqual({ behind: 2, ahead: 3 });
  });

  it("keeps the steps passed while the minimum ahead fits beside them", () => {
    expect(
      fitRows({ behind: rows(2), ahead: rows(10), left: 10, more: 30, room: 300, minAhead: 3 }),
    ).toEqual({ behind: 2, ahead: 7 });
  });

  it("shows the nearest step even in a window too short for it", () => {
    expect(
      fitRows({ behind: rows(2), ahead: rows(4), left: 4, more: 20, room: 10, minAhead: 3 }),
    ).toEqual({ behind: 0, ahead: 1 });
  });
});
