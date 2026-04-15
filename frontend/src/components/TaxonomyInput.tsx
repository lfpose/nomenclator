/**
 * TaxonomyInput component
 * Controlled textarea for taxonomy input with placeholder, label, and optional value
 */

import { useState } from "react";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";

interface TaxonomyInputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  label?: string;
  id?: string;
  rows?: number;
  disabled?: boolean;
}

export function TaxonomyInput({
  value: controlledValue,
  onChange,
  placeholder = "Ventas\nTecnología\nOperaciones\nFinanzas\nRRHH\nOtros",
  label = "Taxonomy (optional)",
  id = "taxonomy",
  rows = 10,
  disabled = false,
}: TaxonomyInputProps) {
  // Use internal state for uncontrolled mode
  const [internalValue, setInternalValue] = useState("");

  // Use controlled value if provided, otherwise use internal state
  const isControlled = controlledValue !== undefined;
  const currentValue = isControlled ? controlledValue : internalValue;

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    onChange?.(newValue);
    if (!isControlled) {
      setInternalValue(newValue);
    }
  };

  return (
    <div className="space-y-2">
      {label && (
        <Label htmlFor={id} className="text-sm font-medium">
          {label}
        </Label>
      )}
      <Textarea
        id={id}
        value={currentValue}
        onChange={handleChange}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        className="font-mono text-sm"
      />
    </div>
  );
}
