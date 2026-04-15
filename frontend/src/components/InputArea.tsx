/**
 * InputArea component
 * Combines DropZone with a collapsible paste textarea
 * Emits { file?, text? } based on user input method
 */

import { useState } from "react";
import { DropZone } from "./DropZone";
import { Button } from "./ui/button";
import { Collapsible, CollapsibleContent } from "./ui/collapsible";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";

interface InputAreaProps {
  onInput: (input: { file?: File; text?: string }) => void;
}

export function InputArea({ onInput }: InputAreaProps) {
  const [isPasteOpen, setIsPasteOpen] = useState(false);
  const [pastedText, setPastedText] = useState("");

  const handleFile = (file: File) => {
    onInput({ file });
    setPastedText("");
  };

  const handleFileClear = () => {
    onInput({});
  };

  const handleTextChange = (text: string) => {
    setPastedText(text);
    onInput({ text });
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone for file upload */}
      <DropZone onFile={handleFile} onClear={handleFileClear} accept=".csv" />

      {/* Paste text collapsible section */}
      <Collapsible open={isPasteOpen} onOpenChange={setIsPasteOpen}>
        <div className="flex items-center justify-between space-x-4">
          <Label htmlFor="paste-text" className="text-sm font-medium">
            Or paste titles
          </Label>
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={() => setIsPasteOpen(!isPasteOpen)}
          >
            {isPasteOpen ? "Hide" : "Show"}
          </Button>
        </div>
        <CollapsibleContent className="mt-2">
          <Textarea
            id="paste-text"
            placeholder="Paste job titles here (one per line)"
            value={pastedText}
            onChange={(e) => handleTextChange(e.target.value)}
            rows={8}
            className="font-mono text-sm max-h-48 overflow-y-auto"
            style={{ fieldSizing: "fixed" } as React.CSSProperties}
          />
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
