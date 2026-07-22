import { ThemeProvider as NextThemesProvider } from "next-themes";
import { useTheme } from "next-themes";

/**
 * App-wide theme provider. Toggles the `.dark` class on <html> (Tailwind is
 * configured with `darkMode: ["class"]`), persists the choice to localStorage
 * under the `theme` key, and follows the OS preference when set to "system".
 *
 * The key is kept in sync with the inline anti-FOUC script in index.html — if
 * you change `storageKey` here, update that script too.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      storageKey="theme"
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}

export { useTheme };
