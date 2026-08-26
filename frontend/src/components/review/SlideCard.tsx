import React from "react";
import { Card, CardContent } from "../ui/card";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";

interface SlideData {
  slide_number: number;
  title: string;
  objective: string;
  transition_in: string;
  narration: string;
  understanding_check: string;
  transition_out: string;
  video_prompt?: string;
  quiz_question?: string;
}

interface SlideCardProps {
  slide: SlideData;
  onChange: (field: keyof SlideData, value: string) => void;
}

export const SlideCard: React.FC<SlideCardProps> = ({ slide, onChange }) => {
  const textFields: { key: keyof SlideData; label: string; placeholder: string; rows: number }[] = [
    { key: "objective", label: "Learning Objective", placeholder: "Learning objective of this slide...", rows: 1 },
    { key: "transition_in", label: "Transition In", placeholder: "Spoken transition into the slide...", rows: 1 },
    { key: "narration", label: "Narration (Spoken Script)", placeholder: "The spoken narrative explanation...", rows: 3 },
    { key: "understanding_check", label: "Understanding Check", placeholder: "Check for understanding question...", rows: 1 },
    { key: "transition_out", label: "Transition Out", placeholder: "Spoken transition out of the slide...", rows: 1 },
    { key: "video_prompt", label: "Video/Visual Prompt (Optional)", placeholder: "Play video command or visual focus...", rows: 1 },
    { key: "quiz_question", label: "Quiz/Poll Question (Optional)", placeholder: "Quick quiz or pop poll question...", rows: 1 },
  ];

  return (
    <Card className="border-border/60 hover:shadow-sm transition-all bg-card">
      <CardContent className="p-4 space-y-4">
        <div className="flex justify-between items-center border-b border-border/40 pb-2">
          <h4 className="font-semibold text-sm text-foreground">
            Slide {slide.slide_number}: {slide.title}
          </h4>
        </div>
        
        <div className="grid grid-cols-1 gap-3">
          {textFields.map((field) => (
            <div key={field.key} className="space-y-1">
              <Label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                {field.label}
              </Label>
              <Textarea
                value={(slide[field.key] as string) || ""}
                onChange={(e) => onChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                rows={field.rows}
                className="resize-y text-sm"
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
