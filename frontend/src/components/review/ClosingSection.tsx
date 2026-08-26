import React from "react";
import { Card, CardContent } from "../ui/card";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";

interface ClosingData {
  summary: string;
  next_steps: string;
  farewell: string;
}

interface ClosingSectionProps {
  data: ClosingData;
  onChange: (field: keyof ClosingData, value: string) => void;
}

export const ClosingSection: React.FC<ClosingSectionProps> = ({ data, onChange }) => {
  const fields: { key: keyof ClosingData; label: string; placeholder: string }[] = [
    { key: "summary", label: "Session Summary", placeholder: "Recap main points..." },
    { key: "next_steps", label: "Next Steps / Tasks", placeholder: "Action items for new hires..." },
    { key: "farewell", label: "Farewell / Close", placeholder: "Spoken farewell remark..." },
  ];

  return (
    <div className="space-y-4">
      {fields.map((field) => (
        <Card key={field.key} className="border-border/40 shadow-none">
          <CardContent className="p-4 space-y-2">
            <Label className="text-xs font-bold text-primary uppercase tracking-wider">
              {field.label}
            </Label>
            <Textarea
              value={data[field.key] || ""}
              onChange={(e) => onChange(field.key, e.target.value)}
              placeholder={field.placeholder}
              rows={2}
              className="resize-y"
            />
          </CardContent>
        </Card>
      ))}
    </div>
  );
};
