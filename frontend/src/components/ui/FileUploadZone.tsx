import { useRef, useState, DragEvent, ChangeEvent } from "react";
import { UploadCloud, X, FileText } from "lucide-react";
import { cn } from "@/utils/cn";

interface FileUploadZoneProps {
  accept?: string;
  multiple?: boolean;
  maxSizeMb?: number;
  onFiles: (files: File[]) => void;
  className?: string;
}

export function FileUploadZone({
  accept,
  multiple = false,
  maxSizeMb = 20,
  onFiles,
  className,
}: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);

  function validate(files: File[]): File[] {
    const maxBytes = maxSizeMb * 1024 * 1024;
    const valid: File[] = [];
    const errs: string[] = [];

    for (const f of files) {
      if (f.size > maxBytes) {
        errs.push(`${f.name} exceeds ${maxSizeMb} MB`);
      } else {
        valid.push(f);
      }
    }

    if (errs.length) setError(errs.join(", "));
    else setError(null);

    return valid;
  }

  function handleFiles(rawFiles: FileList | null) {
    if (!rawFiles) return;
    const files = validate(Array.from(rawFiles));
    if (!files.length) return;
    const list = multiple ? files : [files[0]];
    setSelected(list);
    onFiles(list);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  function removeFile(index: number) {
    const next = selected.filter((_, i) => i !== index);
    setSelected(next);
    onFiles(next);
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
          dragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-accent/30"
        )}
      >
        <UploadCloud className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
        <p className="text-sm font-medium">
          Drag & drop {multiple ? "files" : "a file"} here, or{" "}
          <span className="text-primary underline">click to browse</span>
        </p>
        {accept && (
          <p className="text-xs text-muted-foreground mt-1">
            Accepted: {accept} — max {maxSizeMb} MB
          </p>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={(e: ChangeEvent<HTMLInputElement>) => handleFiles(e.target.files)}
        />
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {selected.length > 0 && (
        <ul className="space-y-1">
          {selected.map((f, i) => (
            <li key={i} className="flex items-center gap-2 text-sm border rounded-md px-3 py-2">
              <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-xs text-muted-foreground shrink-0">
                {(f.size / 1024).toFixed(0)} KB
              </span>
              <button
                type="button"
                onClick={() => removeFile(i)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
