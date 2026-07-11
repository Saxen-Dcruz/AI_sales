module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  settings: { react: { version: '18.2' } },
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
    // This codebase doesn't use PropTypes consistently and has no plans to
    // adopt them — the 700+ pre-existing violations were never actually
    // enforced. Off rather than fixed piecemeal to avoid a false sense of
    // type safety from partial coverage.
    'react/prop-types': 'off',
  },
}
