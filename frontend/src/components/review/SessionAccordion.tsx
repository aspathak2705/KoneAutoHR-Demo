import React from "react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../ui/accordion";
import { OpeningSection } from "./OpeningSection";
import { SlideCard } from "./SlideCard";
import { ClosingSection } from "./ClosingSection";

interface OpeningData {
  greeting: string;
  presenter_intro: string;
  employee_welcome: string;
  audio_check: string;
  ice_breaker: string;
  session_rules: string;
  agenda: string;
}

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

interface ClosingData {
  summary: string;
  next_steps: string;
  farewell: string;
}

interface SessionScriptContent {
  opening: OpeningData;
  slides: SlideData[];
  closing: ClosingData;
}

interface SessionAccordionProps {
  sessionScript: SessionScriptContent;
  onOpeningChange: (field: keyof OpeningData, value: string) => void;
  onSlideChange: (index: number, field: keyof SlideData, value: any) => void;
  onClosingChange: (field: keyof ClosingData, value: string) => void;
}

export const SessionAccordion: React.FC<SessionAccordionProps> = ({
  sessionScript,
  onOpeningChange,
  onSlideChange,
  onClosingChange,
}) => {
  return (
    <Accordion type="multiple" defaultValue={["opening", "slides", "closing"]} className="w-full space-y-4">
      {/* 1. Opening Section Collapsible */}
      <AccordionItem value="opening" className="border border-border/60 rounded-xl px-4 bg-muted/10">
        <AccordionTrigger className="hover:no-underline font-semibold text-base py-4 text-foreground">
          ▼ Session Opening
        </AccordionTrigger>
        <AccordionContent className="pb-6 space-y-4">
          <OpeningSection data={sessionScript.opening} onChange={onOpeningChange} />
        </AccordionContent>
      </AccordionItem>

      {/* 2. Slides Section Collapsible */}
      <AccordionItem value="slides" className="border border-border/60 rounded-xl px-4 bg-muted/10">
        <AccordionTrigger className="hover:no-underline font-semibold text-base py-4 text-foreground">
          ▼ Presentation Slides ({sessionScript.slides.length})
        </AccordionTrigger>
        <AccordionContent className="pb-6 space-y-4">
          <div className="space-y-4">
            {sessionScript.slides.map((slide, index) => (
              <SlideCard
                key={slide.slide_number}
                slide={slide}
                onChange={(field, value) => onSlideChange(index, field, value)}
              />
            ))}
          </div>
        </AccordionContent>
      </AccordionItem>

      {/* 3. Closing Section Collapsible */}
      <AccordionItem value="closing" className="border border-border/60 rounded-xl px-4 bg-muted/10">
        <AccordionTrigger className="hover:no-underline font-semibold text-base py-4 text-foreground">
          ▼ Session Closing
        </AccordionTrigger>
        <AccordionContent className="pb-6 space-y-4">
          <ClosingSection data={sessionScript.closing} onChange={onClosingChange} />
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};
