import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-unused-vars": "off",
      // Guardrail: keep the UI system consolidated. These paths were removed
      // during standardization — the primitives now live at @/components/*,
      // and toasts route through react-hot-toast via @/hooks/useToast.
      "no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "@/components/ui/dialog", message: "Use @/components/dialog (primitives were consolidated to @/components/*)." },
            { name: "@/components/ui/select", message: "Use @/components/select." },
            { name: "@/components/ui/table", message: "Use @/components/table." },
            { name: "@/components/ui/pagination", message: "Use @/components/pagination." },
            { name: "@/components/ui/alert-dialog", message: "Use @/components/alert-dialog." },
            { name: "@/components/toast", message: "Toasts are consolidated on react-hot-toast; use useToast from @/hooks/useToast." },
            { name: "@/components/toaster", message: "Removed. A single react-hot-toast <Toaster> is mounted in App.tsx." },
            { name: "sonner", message: "Toasts are consolidated on react-hot-toast." },
            { name: "antd", message: "Ant Design is not used in this app; use the shadcn/Radix primitives in @/components." },
            { name: "react-flow-renderer", message: "Use reactflow (v11) instead of the deprecated react-flow-renderer." },
          ],
        },
      ],
    },
  }
);
