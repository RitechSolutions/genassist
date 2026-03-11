/** @type {import("prettier").Config} */
module.exports = {
    printWidth: 120,
    tabWidth: 2,
    useTabs: false,
    semi: true,
    singleQuote: true,
    quoteProps: "as-needed",
    jsxSingleQuote: false,
    trailingComma: "es5",
    bracketSpacing: true,
    bracketSameLine: false,
    arrowParens: "always",
    endOfLine: "lf",
    overrides: [
        {
            files: ["*.json", "*.jsonc"],
            options: {
                tabWidth: 2,
            },
        },
        {
            files: ["*.css", "*.scss"],
            options: {
                singleQuote: false,
            },
        },
        {
            files: ["*.html"],
            options: {
                printWidth: 120,
                tabWidth: 4,
                htmlWhitespaceSensitivity: "css",
            },
        },
    ],
};