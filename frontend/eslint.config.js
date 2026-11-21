import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/shared/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, jsxA11y.flatConfigs.strict],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // Spec: no raw HTML injection anywhere in the frontend.
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML is forbidden (SPEC §11).",
        },
        {
          selector: "MemberExpression[property.name='innerHTML']",
          message: "innerHTML is forbidden (SPEC §11).",
        },
        {
          selector: "JSXAttribute[name.name='style']",
          message: "Inline styles break the CSP style-src 'self': use CSS Modules.",
        },
      ],
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "zod",
              message: "Import z from @/shared/lib/zod (jitless: no CSP reports).",
            },
          ],
        },
      ],
      "no-restricted-properties": [
        "error",
        { object: "window", property: "localStorage", message: "Use shared/lib/storage." },
      ],
    },
  },
  {
    // The one place that imports zod and configures it (see the file).
    files: ["src/shared/lib/zod.ts"],
    rules: { "no-restricted-imports": "off" },
  },
  {
    files: ["scripts/**/*.mjs"],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
  prettier,
);
