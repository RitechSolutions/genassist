Custom fonts (plugin-js widget)
================================

This folder holds font files that you bundle into the widget. The widget loads
them through src/font.css (imported from src/main.jsx). Vite embeds referenced
font files into dist/widget.css when you run npm run build.

Why use this folder?
--------------------
Keep all @font-face asset URLs under ./fonts/... relative to src/font.css so
paths stay predictable and the build can resolve and inline them correctly.


Quick steps — bundle a custom font
-----------------------------------
1. Copy your font files here, e.g.:
     src/fonts/MyBrand/MyBrand-Regular.woff2
     src/fonts/MyBrand/MyBrand-Bold.woff2

2. Declare each weight/style in src/font.css (one @font-face per variant):
     @font-face {
       font-family: "MyBrand";
       src: url("./fonts/MyBrand/MyBrand-Regular.woff2") format("woff2");
       font-weight: 400;
       font-style: normal;
     }
     @font-face {
       font-family: "MyBrand";
       src: url("./fonts/MyBrand/MyBrand-Bold.woff2") format("woff2");
       font-weight: 700;
       font-style: normal;
     }

   Use format("truetype") for .ttf and format("woff2") for .woff2.

3. Point the widget theme at that family (widget config / GENASSIST_CONFIG):
     theme: { fontFamily: 'MyBrand, sans-serif' }

4. Rebuild: npm run build
   The faces you declared are included in widget.css; no separate font requests
   are needed at runtime unless you also load fonts from the host page.

5. Optional: align the default stack in src/index.css :root font-family with
   your primary family so any code that does not use the theme still matches.


Multiple weights and italics
-----------------------------
Add one @font-face block per combination of font-weight and font-style you need.
If you omit a weight, the browser may synthesize bold/italic (often lower
quality). Declare 300, 400, 500, 700, etc. explicitly if your UI uses them.


External fonts instead of bundling
-----------------------------------
If you load fonts from the host page (e.g. Google Fonts <link>), you can remove
or empty @font-face rules in src/font.css to shrink widget.css, then set
theme.fontFamily to that family name. Ensure the stylesheet loads before the
widget mounts so text does not flash with a fallback font.


Licensing
---------
Ship only fonts you are licensed to redistribute in your product.
