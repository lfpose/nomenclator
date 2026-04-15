import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ChevronDown, ChevronUp } from "lucide-react";

interface AdvancedPanelProps {
  threshold?: number;
  onThresholdChange?: (value: number) => void;
  titlesPerRequest?: number;
  onTitlesPerRequestChange?: (value: number) => void;
  isDryRun?: boolean;
  onDryRunChange?: (checked: boolean) => void;
}

export function AdvancedPanel({
  threshold = 90,
  onThresholdChange,
  titlesPerRequest = 25,
  onTitlesPerRequestChange,
  isDryRun = false,
  onDryRunChange,
}: AdvancedPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleThresholdChange = (value: number[]) => {
    onThresholdChange?.(value[0]);
  };

  const handleTitlesPerRequestChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value) && value >= 1 && value <= 50) {
      onTitlesPerRequestChange?.(value);
    }
  };

  return (
    <TooltipProvider>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="border rounded-md">
          <Button
            variant="ghost"
            className="w-full justify-between px-4 py-2 font-normal"
            onClick={() => setIsOpen(!isOpen)}
            type="button"
          >
            <span>Advanced</span>
            {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
          <CollapsibleContent className="px-4 pb-4 space-y-4">
            {/* Threshold slider */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger>
                    <div className="cursor-help">
                      <Label htmlFor="threshold" className="cursor-pointer">Fuzzy threshold</Label>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="max-w-xs">
                      Controls how similar two titles must be to merge into one cluster. Higher =
                      stricter (fewer merges). Default 90 works well for most Spanish job title
                      datasets.
                    </p>
                  </TooltipContent>
                </Tooltip>
                <span className="text-sm text-muted-foreground ml-auto">{threshold}</span>
              </div>
              <Slider
                id="threshold"
                min={50}
                max={100}
                step={1}
                value={[threshold]}
                onValueChange={(value) => handleThresholdChange(Array.isArray(value) ? value : [value])}
                className="w-full"
              />
            </div>

            {/* Titles per request input */}
            <div className="space-y-2">
              <Tooltip>
                <TooltipTrigger>
                  <div className="cursor-help">
                    <Label htmlFor="titlesPerRequest" className="cursor-pointer">Titles per request</Label>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="max-w-xs">
                    How many titles to bundle into each AI request. Higher = cheaper but less reliable.
                    Default 25 is the sweet spot.
                  </p>
                </TooltipContent>
              </Tooltip>
              <Input
                id="titlesPerRequest"
                type="number"
                min={1}
                max={50}
                value={titlesPerRequest}
                onChange={handleTitlesPerRequestChange}
                className="w-full"
              />
            </div>

            {/* Dry run switch */}
            <div className="flex items-center space-x-2">
              <Switch id="dryRun" checked={isDryRun} onCheckedChange={onDryRunChange} />
              <Tooltip>
                <TooltipTrigger>
                  <Label htmlFor="dryRun" className="font-normal cursor-help">
                    Dry run (no API cost)
                  </Label>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="max-w-xs">
                    Run the full pipeline with fake results instead of calling the AI. Useful for
                    testing that your CSV uploads correctly. Costs nothing.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>
    </TooltipProvider>
  );
}
