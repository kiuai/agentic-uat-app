import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import type { TestScript, ScriptFormat } from "@/types";
import { useState } from "react";

const FORMAT_LABELS: Record<ScriptFormat, string> = {
  playwright_ts: "Playwright TS",
  playwright_js: "Playwright JS",
  selenium_python: "Selenium",
  pytest: "Pytest",
  robot_framework: "Robot Framework",
  gherkin: "Gherkin",
};

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  IN_REVIEW: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
};

export function TestScriptsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [selectedScript, setSelectedScript] = useState<TestScript | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<ScriptFormat>("playwright_ts");

  const { data: scripts, isLoading } = useQuery({
    queryKey: ["test-scripts", projectId],
    queryFn: () => apiGet<TestScript[]>(`/api/v1/projects/${projectId}/test-scripts`),
  });

  return (
    <div className="flex gap-4 h-full">
      {/* Script list */}
      <div className="w-80 shrink-0">
        <h2 className="text-xl font-bold mb-4">Test Scripts</h2>
        {isLoading ? (
          <p className="text-muted-foreground text-sm">Loading...</p>
        ) : (
          <div className="space-y-2">
            {scripts?.map((script) => (
              <button
                key={script.id}
                onClick={() => {
                  setSelectedScript(script);
                  const firstFormat = Object.keys(script.scripts)[0] as ScriptFormat;
                  if (firstFormat) setSelectedFormat(firstFormat);
                }}
                className={`w-full text-left bg-card border rounded-lg p-3 hover:border-primary transition-colors ${
                  selectedScript?.id === script.id ? "border-primary" : ""
                }`}
              >
                <p className="font-medium text-sm truncate">{script.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[script.status]}`}>
                    {script.status}
                  </span>
                  <span className="text-xs text-muted-foreground">v{script.version}</span>
                </div>
              </button>
            ))}
            {scripts?.length === 0 && (
              <p className="text-muted-foreground text-sm">No scripts yet. Generate from requirements.</p>
            )}
          </div>
        )}
      </div>

      {/* Script viewer */}
      {selectedScript && (
        <div className="flex-1 bg-card border rounded-lg p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium">{selectedScript.title}</h3>
            <div className="flex gap-2">
              {(Object.keys(selectedScript.scripts) as ScriptFormat[]).map((fmt) => (
                <button
                  key={fmt}
                  onClick={() => setSelectedFormat(fmt)}
                  className={`text-xs px-2 py-1 rounded ${
                    selectedFormat === fmt ? "bg-primary text-primary-foreground" : "bg-secondary"
                  }`}
                >
                  {FORMAT_LABELS[fmt] ?? fmt}
                </button>
              ))}
            </div>
          </div>
          <pre className="flex-1 bg-muted rounded p-4 text-xs overflow-auto font-mono">
            {selectedScript.scripts[selectedFormat] ?? "Format not available."}
          </pre>
        </div>
      )}
    </div>
  );
}
