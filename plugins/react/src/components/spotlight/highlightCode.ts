/**
 * A deliberately small, dependency-free syntax highlighter for code blocks in agent
 * replies. It does not parse languages; it recognises the tokens that make code readable
 * at a glance (comments, strings, numbers, keywords, function calls, JSON keys, markup
 * tags), with comment syntax chosen per language family.
 */

export type TokenType = 'comment' | 'string' | 'number' | 'keyword' | 'function' | 'property' | 'tag';

export interface CodeToken {
  text: string;
  type?: TokenType;
}

const HASH_COMMENT_LANGS = [
  'python', 'py', 'bash', 'sh', 'shell', 'zsh', 'console', 'yaml', 'yml', 'ruby', 'rb', 'r',
  'toml', 'dockerfile', 'docker', 'makefile', 'make', 'perl', 'pl', 'powershell', 'ps1', 'ini', 'conf', 'env',
];
const SQL_LANGS = ['sql', 'mysql', 'postgres', 'postgresql', 'pgsql', 'sqlite', 'plsql', 'tsql'];
const MARKUP_LANGS = ['html', 'xml', 'svg', 'vue', 'jsx', 'tsx'];
const NO_KEYWORD_LANGS = ['json', 'jsonc', 'html', 'xml', 'svg', 'text', 'txt', 'plaintext', 'csv', 'markdown', 'md'];

const KEYWORDS = new Set(
  (
    // JS / TS
    'const let var function return if else for while do switch case break continue new class extends ' +
    'import from export default async await try catch finally throw typeof instanceof in of this super ' +
    'null undefined true false void yield static public private protected readonly interface type enum ' +
    'implements abstract declare namespace keyof as is ' +
    // Python
    'def lambda pass None True False and or not elif with global nonlocal raise except print self assert del ' +
    // Rust / Go / C-family
    'fn mut impl struct pub use mod match loop func go defer chan map range select package int float ' +
    'double char bool boolean string long short unsigned void final override virtual using ' +
    // Shell
    'echo then fi done esac export local source sudo'
  ).split(' '),
);

const SQL_KEYWORDS = new Set(
  (
    'select from where insert into values update set delete join left right inner outer full cross on ' +
    'group by order having limit offset as and or not null is in between like ilike exists create table ' +
    'alter drop index view primary key foreign references distinct union all case when then else end ' +
    'asc desc default returning with count sum avg min max true false'
  ).split(' '),
);

const STRING = String.raw`"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|` + '`(?:\\\\.|[^`\\\\])*`';
const NUMBER = String.raw`\b(?:0x[\da-fA-F]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b`;
const IDENT = String.raw`[A-Za-z_$][\w$]*`;
const TAG = String.raw`<\/?[A-Za-z][\w:-]*`;

function commentPattern(lang: string): string {
  if (HASH_COMMENT_LANGS.indexOf(lang) !== -1) return String.raw`#[^\n]*`;
  if (SQL_LANGS.indexOf(lang) !== -1) return String.raw`--[^\n]*|\/\*[\s\S]*?\*\/`;
  if (lang === 'html' || lang === 'xml' || lang === 'svg') return String.raw`<!--[\s\S]*?-->`;
  if (lang === 'json') return String.raw`(?!)`; // JSON has no comments
  return String.raw`\/\/[^\n]*|\/\*[\s\S]*?\*\/`;
}

/** Split `code` into highlighted tokens; unmatched text comes back as plain tokens. */
export function highlightCode(code: string, language?: string): CodeToken[] {
  const lang = (language || '').toLowerCase();
  const isSql = SQL_LANGS.indexOf(lang) !== -1;
  const isMarkup = MARKUP_LANGS.indexOf(lang) !== -1;
  const useKeywords = NO_KEYWORD_LANGS.indexOf(lang) === -1;

  // Group order = priority: comment, string, number, tag, identifier.
  const re = new RegExp(
    `(${commentPattern(lang)})|(${STRING})|(${NUMBER})|(${isMarkup ? TAG : '(?!)'})|(${IDENT})`,
    'g',
  );

  const tokens: CodeToken[] = [];
  const push = (text: string, type?: TokenType) => {
    if (!text) return;
    const last = tokens[tokens.length - 1];
    if (last && !last.type && !type) last.text += text;
    else tokens.push(type ? { text, type } : { text });
  };

  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(code)) !== null) {
    if (m[0] === '') {
      re.lastIndex++;
      continue;
    }
    push(code.slice(last, m.index));
    const rest = code.slice(re.lastIndex);
    if (m[1]) push(m[0], 'comment');
    else if (m[2]) push(m[0], /^\s*:/.test(rest) && !/^\s*::/.test(rest) ? 'property' : 'string');
    else if (m[3]) push(m[0], 'number');
    else if (m[4]) push(m[0], 'tag');
    else {
      const word = m[0];
      const isKeyword = useKeywords && (isSql ? SQL_KEYWORDS.has(word.toLowerCase()) : KEYWORDS.has(word));
      if (isKeyword) push(word, 'keyword');
      else if (useKeywords && /^\s*\(/.test(rest)) push(word, 'function');
      else if (lang === 'json' && (word === 'true' || word === 'false' || word === 'null')) push(word, 'keyword');
      else push(word);
    }
    last = re.lastIndex;
  }
  push(code.slice(last));
  return tokens;
}
