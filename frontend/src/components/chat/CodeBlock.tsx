"use client";

import { useMemo, useState } from "react";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import css from "highlight.js/lib/languages/css";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import python from "highlight.js/lib/languages/python";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";

// Register only the languages a STEM tutor realistically emits — keeps the
// bundle lean vs. the full auto-detect build.
hljs.registerLanguage("bash", bash);
hljs.registerLanguage("c", c);
hljs.registerLanguage("cpp", cpp);
hljs.registerLanguage("css", css);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("python", python);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("xml", xml);

const ALIASES: Record<string, string> = {
  py: "python",
  js: "javascript",
  jsx: "javascript",
  ts: "typescript",
  tsx: "typescript",
  sh: "bash",
  shell: "bash",
  zsh: "bash",
  console: "bash",
  html: "xml",
  svg: "xml",
  "c++": "cpp",
  cc: "cpp",
  h: "cpp",
  hpp: "cpp",
};

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const src = code.replace(/\n$/, "");
  const norm = ALIASES[lang] || lang;

  const html = useMemo(() => {
    try {
      if (norm && hljs.getLanguage(norm)) {
        return hljs.highlight(src, { language: norm }).value;
      }
      return hljs.highlightAuto(src).value;
    } catch {
      return escapeHtml(src);
    }
  }, [src, norm]);

  const [copied, setCopied] = useState(false);
  const copy = (): void => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard
        .writeText(src)
        .then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        })
        .catch(() => {});
    }
  };

  return (
    <pre className="md-code">
      <div className="code-head">
        <span className="code-lang">{lang || "code"}</span>
        <button type="button" className="code-copy" onClick={copy}>
          {copied ? "✓ скопировано" : "copy"}
        </button>
      </div>
      <code className="hljs" dangerouslySetInnerHTML={{ __html: html }} />
    </pre>
  );
}
