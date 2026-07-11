import { FlatCompat } from '@eslint/eslintrc'
import js from '@eslint/js'
import globals from 'globals'

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
  recommendedConfig: js.configs.recommended,
})

export default [
  { ignores: ['dist'] },
  ...compat.extends(
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
  ),
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      // Equivalent to env: { browser: true, es2020: true } under the old .eslintrc.cjs
      globals: { ...globals.browser, ...globals.es2020 },
    },
    settings: { react: { version: '18.2' } },
    plugins: {
      'react-refresh': (await import('eslint-plugin-react-refresh')).default,
      'react-hooks': (await import('eslint-plugin-react-hooks')).default,
    },
    rules: {
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      // Pinned to exactly what eslint-plugin-react-hooks@4.6.2's `recommended`
      // enforced, NOT the current plugin's `recommended` (7.x adds several new
      // stricter rules, e.g. set-state-in-effect, that this codebase was never
      // held to — adopting them wholesale here would be a second large,
      // unrelated lint-fixing project). The plugin itself had to jump to 7.x
      // for ESLint 10 support; no smaller bump exists.
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // This codebase doesn't use PropTypes consistently and has no plans to
      // adopt them — the 700+ pre-existing violations were never actually
      // enforced. Off rather than fixed piecemeal to avoid a false sense of
      // type safety from partial coverage.
      'react/prop-types': 'off',
    },
  },
  {
    // Pure service/API layer, not React components — despite the .jsx
    // extension it exports no components at all, so the Fast Refresh rule
    // doesn't apply here.
    files: ['**/services/**/*.jsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
]
