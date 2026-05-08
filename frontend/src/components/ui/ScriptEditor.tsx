import Editor from "@monaco-editor/react";
import type { ScriptFormat } from "@/types";
import { cn } from "@/utils/cn";

const FORMAT_LANGUAGE: Record<ScriptFormat, string> = {
  playwright_ts: "typescript",
  playwright_js: "javascript",
  selenium_python: "python",
  pytest: "python",
  robot_framework: "robotframework",
  gherkin: "gherkin",
};

interface ScriptEditorProps {
  value: string;
  onChange?: (value: string) => void;
  format?: ScriptFormat;
  readOnly?: boolean;
  height?: string;
  className?: string;
}

export function ScriptEditor({
  value,
  onChange,
  format,
  readOnly = false,
  height = "400px",
  className,
}: ScriptEditorProps) {
  const language = format ? (FORMAT_LANGUAGE[format] ?? "plaintext") : "plaintext";

  return (
    <div className={cn("rounded-lg overflow-hidden border", className)} style={{ height }}>
      <Editor
        height="100%"
        language={language}
        value={value}
        onChange={(v) => onChange?.(v ?? "")}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          theme: "vs-dark",
          padding: { top: 8, bottom: 8 },
        }}
        loading={
          <div className="flex items-center justify-center h-full bg-[#1e1e1e] text-gray-400 text-sm">
            Loading editor…
          </div>
        }
      />
    </div>
  );
}
