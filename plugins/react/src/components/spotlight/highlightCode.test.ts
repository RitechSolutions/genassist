import { describe, expect, it } from 'vitest';
import { highlightCode } from './highlightCode';

const typed = (code: string, lang?: string) =>
  highlightCode(code, lang)
    .filter((t) => t.type)
    .map((t) => `${t.type}:${t.text}`);

describe('highlightCode', () => {
  it('round-trips the source text exactly', () => {
    const src = 'const x = foo("a // not a comment", 42); // done\n/* block */\nreturn x;';
    expect(highlightCode(src, 'js').map((t) => t.text).join('')).toBe(src);
  });

  it('marks JS keywords, strings, numbers, calls and comments', () => {
    expect(typed('const x = foo("hi", 42); // note', 'javascript')).toEqual([
      'keyword:const',
      'function:foo',
      'string:"hi"',
      'number:42',
      'comment:// note',
    ]);
  });

  it('does not treat comment markers inside strings as comments', () => {
    expect(typed('url = "http://x.io"', 'python')).toEqual(['string:"http://x.io"']);
  });

  it('uses # comments for Python and shell, but not for JS', () => {
    expect(typed('def f():  # hi', 'python')).toEqual(['keyword:def', 'function:f', 'comment:# hi']);
    expect(typed('echo $HOME # path', 'bash')).toEqual(['keyword:echo', 'comment:# path']);
    expect(typed('a # b', 'js').some((t) => t.startsWith('comment'))).toBe(false);
  });

  it('highlights SQL keywords case-insensitively with -- comments', () => {
    expect(typed('SELECT id FROM users -- all', 'sql')).toEqual(['keyword:SELECT', 'keyword:FROM', 'comment:-- all']);
  });

  it('marks JSON keys as properties and values as strings', () => {
    expect(typed('{"name": "Ann", "ok": true, "n": 3}', 'json')).toEqual([
      'property:"name"',
      'string:"Ann"',
      'property:"ok"',
      'keyword:true',
      'property:"n"',
      'number:3',
    ]);
  });

  it('marks tags in markup', () => {
    expect(typed('<div class="a"></div>', 'html')).toEqual(['tag:<div', 'string:"a"', 'tag:</div']);
  });

  it('leaves unknown plain text untouched', () => {
    expect(highlightCode('just words here', 'text')).toEqual([{ text: 'just words here' }]);
  });
});
