import js from "@eslint/js";
import importX from "eslint-plugin-import-x";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import prettier from "eslint-config-prettier";
import { createTypeScriptImportResolver } from "eslint-import-resolver-typescript";
import globals from "globals";
import tseslint from "typescript-eslint";

// Cyrillic anywhere a user can see it. An error, not a warning: the catalogues exist, so there
// is somewhere for the text to go, and t() is the way it gets there.
const CYRILLIC = /[\u0400-\u04FF]/.source;
const noCyrillic = [
  {
    selector: `JSXText[value=/${CYRILLIC}/]`,
    message: "UI text belongs in a locale catalogue. Add a key to locales/*.json and call t().",
  },
  {
    selector: `Literal[value=/${CYRILLIC}/]`,
    message: "UI text belongs in a locale catalogue. Add a key to locales/*.json and call t().",
  },
  {
    selector: `TemplateElement[value.raw=/${CYRILLIC}/]`,
    message: "UI text belongs in a locale catalogue. Add a key with a {placeholder} and call t().",
  },
];

export default tseslint.config(
  { ignores: ["dist", "node_modules", "*.config.js", "*.config.ts"] },

  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  react.configs.flat.recommended,
  react.configs.flat["jsx-runtime"],
  reactHooks.configs["recommended-latest"],
  jsxA11y.flatConfigs.recommended,
  importX.flatConfigs.recommended,
  prettier,

  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser },
      parserOptions: {
        ecmaFeatures: { jsx: true },
        // The typed rules load the types themselves, from the same program tsc uses.
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    settings: {
      react: { version: "detect" },
      // The tsconfig resolver is what teaches import-x about the "@/" alias and about
      // extensionless imports; without it every import reads as unresolved.
      "import-x/resolver-next": [
        createTypeScriptImportResolver({ alwaysTryTypes: true, project: "./tsconfig.json" }),
      ],
    },
    rules: {
      "react/prop-types": "off",
      "react-hooks/exhaustive-deps": "error",

      // Dropping a key by destructuring it out (`const { id, ...rest } = marker`) is how this
      // codebase omits a field without rebuilding the object and losing its key order.
      "@typescript-eslint/no-unused-vars": ["error", { ignoreRestSiblings: true }],

      // The layer boundaries: shared/** knows
      // nothing about a feature, and features know nothing about each other. Anything two
      // features share moves into shared/**.
      "import-x/no-restricted-paths": [
        "error",
        {
          zones: [
            {
              target: "./src/shared",
              from: ["./src/features", "./src/app"],
              message:
                "shared/** is the bottom layer: it must not know about a feature or the app shell.",
            },
            {
              target: "./src/features/panel",
              from: ["./src/features/editor", "./src/features/steps"],
              message: "Features do not import each other. Move what they share into shared/**.",
            },
            {
              target: "./src/features/editor",
              from: ["./src/features/panel", "./src/features/steps"],
              message: "Features do not import each other. Move what they share into shared/**.",
            },
            {
              target: "./src/features/steps",
              from: ["./src/features/panel", "./src/features/editor"],
              message: "Features do not import each other. Move what they share into shared/**.",
            },
          ],
        },
      ],

      "import-x/order": [
        "error",
        {
          groups: ["builtin", "external", "internal", "parent", "sibling", "index"],
          alphabetize: { order: "asc", caseInsensitive: true },
          "newlines-between": "always",
        },
      ],

      // confirm()/alert() block the page's script and cannot be styled. useConfirm has the app's
      // own dialog.
      "no-restricted-globals": [
        "error",
        { name: "confirm", message: "Use shared/hooks/useConfirm instead." },
        { name: "alert", message: "Use a toast instead." },
      ],

      "no-restricted-syntax": ["error", ...noCyrillic],
    },
  },

  // dev/ is mock data standing in for Python, so it may hold whatever the real payloads hold.
  // The catalogues themselves live in ../locales, outside this config's reach.
  {
    files: ["src/**/dev/**"],
    rules: { "no-restricted-syntax": "off" },
  },

  // The confirm wrapper is the one place allowed to call the global.
  {
    files: ["src/shared/hooks/useConfirm.*"],
    rules: { "no-restricted-globals": "off" },
  },

  {
    files: ["**/*.test.{ts,tsx}"],
    languageOptions: { globals: { ...globals.node } },
  },
);
