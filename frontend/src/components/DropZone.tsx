import { useCallback, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Upload, X } from "lucide-react";

interface DropZoneProps {
  onFile: (file: File) => void;
  onClear?: () => void;
  accept?: string;
}

export function DropZone({ onFile, onClear, accept = ".csv" }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setFileName(file.name);
        onFile(file);
      }
    },
    [onFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file) {
        setFileName(file.name);
        onFile(file);
      }
    },
    [onFile],
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setFileName(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onClear?.();
    },
    [onClear],
  );

  if (fileName) {
    return (
      <div className="border-2 border-primary/50 rounded-lg p-6 flex items-center justify-between bg-primary/5">
        <div className="flex items-center gap-3">
          <Upload className="h-5 w-5 text-primary" />
          <span className="text-sm font-medium">{fileName}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClear}
          type="button"
          aria-label="Remove file"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`
        border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
        ${isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary"}
      `}
    >
      <input
        type="file"
        ref={fileInputRef}
        accept={accept}
        onChange={handleFileChange}
        className="hidden"
      />
      <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">
        Drop a CSV here or click to browse
      </p>
    </div>
  );
}
