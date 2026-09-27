/**
 * Shared Vitest setup.
 *
 * Vitest runs with `globals: false`, so Testing Library's own auto-cleanup never registers
 * itself: without the hook below, a component left mounted by one test is still in the document
 * when the next one queries it, and the failure shows up in the innocent test.
 */

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);
