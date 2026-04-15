import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface RowSubsetSelectorProps {
  mode: "all" | "first_n" | "random_n";
  n: number | null;
  onModeChange: (mode: "all" | "first_n" | "random_n") => void;
  onNChange: (n: number | null) => void;
}

export function RowSubsetSelector({
  mode,
  n,
  onModeChange,
  onNChange,
}: RowSubsetSelectorProps) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">Row selection</Label>
      <div className="flex items-center gap-3">
        <Select
          value={mode}
          onValueChange={(val) => onModeChange(val as "all" | "first_n" | "random_n")}
          items={{
            all: "All rows",
            first_n: "First N rows",
            random_n: "Random sample of N rows",
          }}
        >
          <SelectTrigger className="w-52 bg-background">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All rows</SelectItem>
            <SelectItem value="first_n">First N rows</SelectItem>
            <SelectItem value="random_n">Random sample of N rows</SelectItem>
          </SelectContent>
        </Select>

        {mode !== "all" && (
          <Input
            type="number"
            min={1}
            value={n ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              onNChange(val === "" ? null : parseInt(val, 10));
            }}
            placeholder="N"
            className="w-24"
          />
        )}
      </div>
    </div>
  );
}
