import { createContext, useContext } from "react";

/**
 * True for everything rendered inside AppLayout (sidebar + main area). Loaders
 * there must stay inside the layout: the full-screen splash would cover the
 * sidebar, and a guard that never settles (e.g. an answered empty permission
 * list) would leave the user with no navigation and no way to sign out.
 */
export const AppShellContext = createContext(false);

export const useIsInAppShell = () => useContext(AppShellContext);
