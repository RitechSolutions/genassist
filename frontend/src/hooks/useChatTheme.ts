import { useEffect, useMemo, useState } from "react";
import type { ChatTheme } from "genassist-chat-react";
import { useTheme } from "@/context/ThemeProvider";

/**
 * Chat widget palettes for the app's light and dark modes.
 *
 * The chat plugin has no dark mode of its own: it reads no `prefers-color-scheme`
 * media query and exposes no `darkMode` prop. It renders whatever colors the host
 * passes and silently falls back to light defaults for any token left out. So
 * following the app theme means handing it a full palette per mode — including
 * the four tokens added for dark mode (userBubbleColor, inputBackgroundColor,
 * borderColor, mutedTextColor). Omitting those is what pins the widget to light.
 *
 * Surface colors match the palette validated in the plugin's example app. The
 * dark `primaryColor` is a lightened take on the brand blue — #173DED is close
 * to unreadable against a dark surface.
 */
export const LIGHT_CHAT_THEME: ChatTheme = {
  primaryColor: "#173DED",
  secondaryColor: "#f5f5f5",
  backgroundColor: "#ffffff",
  textColor: "#000000",
  fontFamily: "Inter, sans-serif",
  fontSize: "15px",
  userBubbleColor: "#E4E4E7",
  inputBackgroundColor: "#ffffff",
  borderColor: "#e5e7eb",
  mutedTextColor: "#6b7280",
};

export const DARK_CHAT_THEME: ChatTheme = {
  primaryColor: "#5B7CFF",
  secondaryColor: "#1f2023",
  backgroundColor: "#141517",
  textColor: "#f4f4f5",
  fontFamily: "Inter, sans-serif",
  fontSize: "15px",
  userBubbleColor: "#3f3f46",
  inputBackgroundColor: "#26272b",
  borderColor: "#3f3f46",
  mutedTextColor: "#a1a1aa",
};

export function chatThemeForMode(mode: "light" | "dark"): ChatTheme {
  return mode === "dark" ? DARK_CHAT_THEME : LIGHT_CHAT_THEME;
}

/**
 * The app's resolved color mode ("system" collapsed to light/dark). A `mounted`
 * guard keeps the first render on light until next-themes has read the persisted
 * choice, mirroring how ThemeToggle avoids showing the wrong option.
 */
export function useColorMode(): "light" | "dark" {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  return mounted && resolvedTheme === "dark" ? "dark" : "light";
}

/**
 * Chat theme that follows the app's light/dark mode. `overrides` layers on top,
 * for call sites that pin brand-specific values (font, header color).
 */
export function useChatTheme(overrides?: Partial<ChatTheme>): ChatTheme {
  const mode = useColorMode();

  return useMemo(
    () => ({ ...chatThemeForMode(mode), ...overrides }),
    // Overrides are written inline at call sites, so compare by value rather
    // than identity — otherwise a fresh object literal rebuilds every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mode, JSON.stringify(overrides ?? {})]
  );
}
