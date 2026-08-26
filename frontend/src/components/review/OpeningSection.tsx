import React from "react";
import { Card, CardContent } from "../ui/card";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";

interface OpeningData {
  greeting: string;
  presenter_intro: string;
  employee_welcome: string;
  audio_check: string;
  ice_breaker: string;
  session_rules: string;
  agenda: string;
}

interface OpeningSectionProps {
  data: OpeningData;
  onChange: (field: keyof OpeningData, value: string) => void;
}

export const OpeningSection: React.FC<OpeningSectionProps> = ({ data, onChange }) => {
  const fields: { key: keyof OpeningData; label: string; placeholder: string }[] = [
    { key: "greeting", label: "Greeting", placeholder: "Warm welcome to start the session..." },
    { key: "presenter_intro", label: "Presenter Introduction", placeholder: "Who you are..." },
    { key: "employee_welcome", label: "Employee Welcome", placeholder: "Welcome message mentioning new hires..." },
    { key: "audio_check", label: "Audio Check", placeholder: "Verify everyone can hear you..." },
    { key: "ice_breaker", label: "Ice Breaker Activity", placeholder: "Ask an engaging question..." },
    { key: "session_rules", label: "Session Rules", placeholder: "Meeting guidelines..." },
    { key: "agenda", label: "Agenda", placeholder: "What will be covered today..." },
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
