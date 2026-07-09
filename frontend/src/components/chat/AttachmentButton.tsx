"use client";

import { useRef, useState } from "react";
import { ingestFile, type IngestResponse } from "@/lib/api";

interface Props {
  onIngested: (result: IngestResponse) => void;
  disabled?: boolean;
}

const ACCEPT = ".pdf,.docx,.png,.jpg,.jpeg,.webp,.gif,.txt,.md";
const MAX_MB = 20;

export function AttachmentButton({ onIngested, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const pick = () => {
    setErr(null);
    inputRef.current?.click();
  };

  const onChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      setErr(`Файл больше ${MAX_MB}MB`);
      return;
    }
    setBusy(true);
    try {
      const result = await ingestFile(file);
      onIngested(result);
    } catch (x) {
      setErr(x instanceof Error ? x.message : "Загрузка не удалась");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={pick}
        disabled={disabled || busy}
        className="cbtn cbtn-ghost"
        title="Прикрепить файл: PDF · Word · PNG/JPG · TXT/MD (макс. 20MB)"
        aria-label="attach file"
        style={{
          opacity: disabled || busy ? 0.5 : 1,
          fontSize: 22,
          padding: "4px 10px",
          lineHeight: 1,
          minWidth: 44,
          minHeight: 44,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {busy ? "⋯" : "📎"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        onChange={onChange}
        style={{ display: "none" }}
      />
      {err && (
        <span
          className="ghost ml-2"
          style={{ color: "var(--error)", fontSize: 12 }}
          title={err}
        >
          ⚠ {err.slice(0, 40)}
        </span>
      )}
    </>
  );
}
