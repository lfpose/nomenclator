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
    // Clear pasted text when file is selected
    setPastedText("");
  };

  const handleTextChange = (text: string) => {
    setPastedText(text);
    onInput({ text });
  };

  const handleTogglePaste = () => {
    setIsPasteOpen(!isPasteOpen);
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone for file upload */}
      <DropZone onFile={handleFile} accept=".csv" />

      {/* Paste text collapsible section */}
      <Collapsible open={isPasteOpen} onOpenChange={setIsPasteOpen}>
        <div className="flex items-center justify-between space-x-4">
          <Label htmlFor="paste-text" className="text-sm font-medium">
            Or paste text
          </Label>
          <Button
            variant="ghost"
            size="sm"
            type="button"
            onClick={handleTogglePaste}
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
            rows={10}
            className="font-mono text-sm"
          />
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
