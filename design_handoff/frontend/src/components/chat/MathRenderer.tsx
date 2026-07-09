"use client";

import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface MathRendererProps {
  content: string;
}

/**
 * Renders text with inline ($...$) and block ($$...$$) LaTeX math.
 * Non-math text is passed through as-is.
 */
export function MathRenderer({ content }: MathRendererProps) {
  const rendered = useMemo(() => renderMathContent(content), [content]);

  return (
    <span
      className="math-content"
      dangerouslySetInnerHTML={{ __html: rendered }}
    />
  );
}

function renderMathContent(text: string): string {
  // First handle block math ($$...$$)
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), {
        displayMode: true,
        throwOnError: false,
        trust: true,
      });
    } catch {
      return `<code class="text-red-400">${escapeHtml(tex)}</code>`;
    }
  });

  // Then handle inline math ($...$) — avoid matching $$
  result = result.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), {
        displayMode: false,
        throwOnError: false,
        trust: true,
      });
    } catch {
      return `<code class="text-red-400">${escapeHtml(tex)}</code>`;
    }
  });

  // Convert newlines to <br>
  result = result.replace(/\n/g, "<br>");

  return result;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
