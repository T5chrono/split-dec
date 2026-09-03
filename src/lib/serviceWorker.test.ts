import { describe, it, expect, vi } from "vitest";
import { registerServiceWorker } from "./serviceWorker";

/** A `window` stand-in that hands back the `load` listener it was given. */
function fakeWindow() {
  const listeners: Array<() => void> = [];
  return {
    target: {
      addEventListener: (type: string, listener: () => void) => {
        if (type === "load") listeners.push(listener);
      },
    } as Pick<Window, "addEventListener">,
    fireLoad: () => listeners.forEach((listener) => listener()),
    count: () => listeners.length,
  };
}

describe("registerServiceWorker", () => {
  it("waits for load rather than competing with first paint", () => {
    const register = vi.fn().mockResolvedValue({});
    const win = fakeWindow();

    registerServiceWorker({ register } as unknown as ServiceWorkerContainer, win.target);
    expect(register).not.toHaveBeenCalled();

    win.fireLoad();
    expect(register).toHaveBeenCalledWith("/sw.js", { scope: "/" });
  });

  it("swallows a refusal instead of raising an unhandled rejection", () => {
    // The regression this module exists for (SPLITDEC-FRONTEND-2): the script
    // vite-plugin-pwa injects attaches nothing to the promise, so an in-app
    // browser that rejects `register` produced a Sentry issue out of a browser
    // capability this app does not need.
    //
    // Asserted with a thenable that records whether a rejection handler was
    // attached at all, rather than by watching for an `unhandledRejection`:
    // vitest installs its own handler for those, so a test waiting on one
    // passes whether or not the code catches anything. Recording both `then`
    // and `catch` keeps the assertion about handling the rejection rather than
    // about the syntax used to handle it — `await` in a `try` would satisfy it
    // too, and dropping the handler is the only thing that fails it.
    let handled = false;
    const refusal: Record<string, unknown> = {
      then: (_onFulfilled: unknown, onRejected: unknown) => {
        handled ||= typeof onRejected === "function";
        return refusal;
      },
      catch: (onRejected: unknown) => {
        handled ||= typeof onRejected === "function";
        return refusal;
      },
    };
    const register = vi.fn().mockReturnValue(refusal);
    const win = fakeWindow();

    registerServiceWorker({ register } as unknown as ServiceWorkerContainer, win.target);
    win.fireLoad();

    expect(register).toHaveBeenCalled();
    expect(handled).toBe(true);
  });

  it("does nothing where service workers are unsupported", () => {
    const win = fakeWindow();
    registerServiceWorker(undefined, win.target);
    expect(win.count()).toBe(0);
  });
});
