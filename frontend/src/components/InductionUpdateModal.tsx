import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { 
  FileText, 
  Volume2, 
  Upload, 
  Layers, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  FileDiff,
  PlusCircle,
  MinusCircle,
  Edit3
} from "lucide-react";

interface InductionUpdateModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  totalSlides?: number;
  onUpdateSuccess?: () => void;
}

interface SlideChange {
  slide_index?: number;
  old_slide_index?: number;
  status: "UNCHANGED" | "MODIFIED" | "ADDED" | "REMOVED";
  title: string;
  details: string;
}

interface DiffSummary {
  unchanged: number;
  modified: number;
  added: number;
  removed: number;
  total_new_slides: number;
}

export function InductionUpdateModal({
  isOpen,
  onClose,
  sessionId,
  totalSlides = 37,
  onUpdateSuccess,
}: InductionUpdateModalProps) {
  const [activeTab, setActiveTab] = useState<string>("single");

  // Single Slide State
  const [targetSlide, setTargetSlide] = useState<string>("1");
  const [singleSlideFile, setSingleSlideFile] = useState<File | null>(null);
  const [isSubmittingSingle, setIsSubmittingSingle] = useState(false);

  // Full PPT State
  const [pptFile, setPptFile] = useState<File | null>(null);
  const [isAnalyzingPpt, setIsAnalyzingPpt] = useState(false);
  const [isApplyingPpt, setIsApplyingPpt] = useState(false);
  const [diffSummary, setDiffSummary] = useState<DiffSummary | null>(null);
  const [diffChanges, setDiffChanges] = useState<SlideChange[]>([]);

  // Audio Update State
  const [targetAudioSlide, setTargetAudioSlide] = useState<string>("1");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isSubmittingAudio, setIsSubmittingAudio] = useState(false);

  // Handlers
  const handleSingleSlideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!singleSlideFile) {
      toast.error("Please select a PowerPoint file containing the replacement slide.");
      return;
    }

    setIsSubmittingSingle(true);
    const formData = new FormData();
    formData.append("target_slide_number", targetSlide);
    formData.append("file", singleSlideFile);

    try {
      const response = await fetch(`/api/v1/induction-update/${sessionId}/single-slide`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to update single slide");
      }

      const res = await response.json();
      toast.success(res.message || `Slide ${targetSlide} updated successfully!`);
      setSingleSlideFile(null);
      if (onUpdateSuccess) onUpdateSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.message || "Failed to update slide");
    } finally {
      setIsSubmittingSingle(false);
    }
  };

  const handleAnalyzePpt = async () => {
    if (!pptFile) {
      toast.error("Please upload a revised PowerPoint presentation.");
      return;
    }

    setIsAnalyzingPpt(true);
    const formData = new FormData();
    formData.append("file", pptFile);

    try {
      const response = await fetch(`/api/v1/induction-update/${sessionId}/analyze-ppt`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to analyze presentation");
      }

      const data = await response.json();
      setDiffSummary(data.summary);
      setDiffChanges(data.changes || []);
      toast.success("Presentation compared successfully. Review detected changes.");
    } catch (err: any) {
      toast.error(err.message || "PPT analysis failed");
    } finally {
      setIsAnalyzingPpt(false);
    }
  };

  const handleApplyPpt = async () => {
    if (!pptFile) return;

    setIsApplyingPpt(true);
    const formData = new FormData();
    formData.append("file", pptFile);

    try {
      const response = await fetch(`/api/v1/induction-update/${sessionId}/apply-ppt`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to apply presentation changes");
      }

      const data = await response.json();
      toast.success(data.message || "Updated presentation successfully applied!");
      setPptFile(null);
      setDiffSummary(null);
      setDiffChanges([]);
      if (onUpdateSuccess) onUpdateSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.message || "Failed to apply PPT");
    } finally {
      setIsApplyingPpt(false);
    }
  };

  const handleAudioSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!audioFile) {
      toast.error("Please select an audio file.");
      return;
    }

    setIsSubmittingAudio(true);
    const formData = new FormData();
    formData.append("target_slide_number", targetAudioSlide);
    formData.append("file", audioFile);

    try {
      const response = await fetch(`/api/v1/induction-update/${sessionId}/slide-audio`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to update slide audio");
      }

      const data = await response.json();
      toast.success(data.message || `Audio for slide ${targetAudioSlide} updated!`);
      setAudioFile(null);
      if (onUpdateSuccess) onUpdateSuccess();
      onClose();
    } catch (err: any) {
      toast.error(err.message || "Failed to update audio");
    } finally {
      setIsSubmittingAudio(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <RefreshCw className="h-5 w-5 text-primary" /> Update Existing Induction
          </DialogTitle>
          <DialogDescription className="text-xs">
            Incrementally update slides or audio without regenerating the entire induction package.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full mt-2">
          <TabsList className="grid grid-cols-3 w-full">
            <TabsTrigger value="single" className="text-xs flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" /> Single Slide
            </TabsTrigger>
            <TabsTrigger value="full" className="text-xs flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5" /> Full Presentation
            </TabsTrigger>
            <TabsTrigger value="audio" className="text-xs flex items-center gap-1.5">
              <Volume2 className="h-3.5 w-3.5" /> Slide Audio Only
            </TabsTrigger>
          </TabsList>

          {/* TAB 1: SINGLE SLIDE */}
          <TabsContent value="single" className="space-y-4 pt-3">
            <div className="p-3 bg-muted/40 rounded-lg text-xs space-y-1 text-muted-foreground border">
              <p className="font-semibold text-foreground">Atomic Slide Swap</p>
              <p>Replaces only the chosen slide in the presentation deck, re-exports its thumbnail, and flags its narration for review. Unchanged slides remain completely untouched.</p>
            </div>

            <form onSubmit={handleSingleSlideSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="target-slide" className="text-xs">Target Slide Number</Label>
                  <Select value={targetSlide} onValueChange={setTargetSlide}>
                    <SelectTrigger id="target-slide" className="h-9 text-xs">
                      <SelectValue placeholder="Select slide" />
                    </SelectTrigger>
                    <SelectContent className="max-h-56">
                      {Array.from({ length: totalSlides }, (_, i) => i + 1).map((num) => (
                        <SelectItem key={num} value={String(num)} className="text-xs">
                          Slide {num}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="single-file" className="text-xs">Revised Slide PPTX</Label>
                  <Input
                    id="single-file"
                    type="file"
                    accept=".pptx,.ppt"
                    className="h-9 text-xs cursor-pointer"
                    onChange={(e) => setSingleSlideFile(e.target.files?.[0] || null)}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmittingSingle}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={!singleSlideFile || isSubmittingSingle}>
                  {isSubmittingSingle ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1.5" /> Updating Slide...
                    </>
                  ) : (
                    <>
                      <Upload className="h-3.5 w-3.5 mr-1.5" /> Update Target Slide
                    </>
                  )}
                </Button>
              </div>
            </form>
          </TabsContent>

          {/* TAB 2: FULL PRESENTATION */}
          <TabsContent value="full" className="space-y-4 pt-3">
            <div className="p-3 bg-muted/40 rounded-lg text-xs space-y-1 text-muted-foreground border">
              <p className="font-semibold text-foreground">Selective Presentation Sync</p>
              <p>Compare an updated PPT deck with the current induction. Unchanged slides keep their existing audio and assets. Modified or new slides are highlighted for confirmation.</p>
            </div>

            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="full-ppt-file" className="text-xs">Upload Revised Presentation (.pptx)</Label>
                <div className="flex gap-2">
                  <Input
                    id="full-ppt-file"
                    type="file"
                    accept=".pptx,.ppt"
                    className="h-9 text-xs cursor-pointer flex-1"
                    onChange={(e) => {
                      setPptFile(e.target.files?.[0] || null);
                      setDiffSummary(null);
                      setDiffChanges([]);
                    }}
                  />
                  <Button 
                    type="button" 
                    size="sm" 
                    variant="secondary"
                    onClick={handleAnalyzePpt}
                    disabled={!pptFile || isAnalyzingPpt || isApplyingPpt}
                  >
                    {isAnalyzingPpt ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1.5" /> Comparing...
                      </>
                    ) : (
                      <>
                        <FileDiff className="h-3.5 w-3.5 mr-1.5" /> Compare Deck
                      </>
                    )}
                  </Button>
                </div>
              </div>

              {diffSummary && (
                <div className="space-y-3 pt-2">
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="p-2 border rounded-md bg-emerald-50/50 border-emerald-200">
                      <div className="text-xs text-emerald-800 font-semibold">{diffSummary.unchanged}</div>
                      <div className="text-[10px] text-muted-foreground">Unchanged</div>
                    </div>
                    <div className="p-2 border rounded-md bg-amber-50/50 border-amber-200">
                      <div className="text-xs text-amber-800 font-semibold">{diffSummary.modified}</div>
                      <div className="text-[10px] text-muted-foreground">Modified</div>
                    </div>
                    <div className="p-2 border rounded-md bg-blue-50/50 border-blue-200">
                      <div className="text-xs text-blue-800 font-semibold">{diffSummary.added}</div>
                      <div className="text-[10px] text-muted-foreground">Added</div>
                    </div>
                    <div className="p-2 border rounded-md bg-rose-50/50 border-rose-200">
                      <div className="text-xs text-rose-800 font-semibold">{diffSummary.removed}</div>
                      <div className="text-[10px] text-muted-foreground">Removed</div>
                    </div>
                  </div>

                  <div className="border rounded-md max-h-48 overflow-y-auto divide-y text-xs">
                    {diffChanges.map((change, idx) => (
                      <div key={idx} className="p-2 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 truncate">
                          {change.status === "UNCHANGED" && (
                            <Badge variant="outline" className="text-emerald-700 border-emerald-300 text-[10px] px-1 py-0 h-4">
                              Same
                            </Badge>
                          )}
                          {change.status === "MODIFIED" && (
                            <Badge variant="outline" className="text-amber-700 border-amber-300 text-[10px] px-1 py-0 h-4">
                              <Edit3 className="h-2.5 w-2.5 mr-0.5 inline" /> Mod
                            </Badge>
                          )}
                          {change.status === "ADDED" && (
                            <Badge variant="outline" className="text-blue-700 border-blue-300 text-[10px] px-1 py-0 h-4">
                              <PlusCircle className="h-2.5 w-2.5 mr-0.5 inline" /> Add
                            </Badge>
                          )}
                          {change.status === "REMOVED" && (
                            <Badge variant="outline" className="text-rose-700 border-rose-300 text-[10px] px-1 py-0 h-4">
                              <MinusCircle className="h-2.5 w-2.5 mr-0.5 inline" /> Del
                            </Badge>
                          )}
                          <span className="font-medium text-foreground truncate">
                            {change.slide_index ? `Slide ${change.slide_index}: ` : ""} {change.title}
                          </span>
                        </div>
                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                          {change.details}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isApplyingPpt}>
                      Cancel
                    </Button>
                    <Button 
                      type="button" 
                      size="sm" 
                      onClick={handleApplyPpt}
                      disabled={isApplyingPpt}
                      className="bg-primary hover:bg-primary/90"
                    >
                      {isApplyingPpt ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1.5" /> Applying Updates...
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" /> Confirm & Apply Changes
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </TabsContent>

          {/* TAB 3: SLIDE AUDIO ONLY */}
          <TabsContent value="audio" className="space-y-4 pt-3">
            <div className="p-3 bg-muted/40 rounded-lg text-xs space-y-1 text-muted-foreground border">
              <p className="font-semibold text-foreground">Audio-Only Calibration</p>
              <p>Replace narration for a single slide (WAV or MP3). Slide visual remains unchanged. Timeline offsets and master audio are dynamically recalibrated.</p>
            </div>

            <form onSubmit={handleAudioSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="audio-target-slide" className="text-xs">Target Slide</Label>
                  <Select value={targetAudioSlide} onValueChange={setTargetAudioSlide}>
                    <SelectTrigger id="audio-target-slide" className="h-9 text-xs">
                      <SelectValue placeholder="Select slide" />
                    </SelectTrigger>
                    <SelectContent className="max-h-56">
                      {Array.from({ length: totalSlides }, (_, i) => i + 1).map((num) => (
                        <SelectItem key={num} value={String(num)} className="text-xs">
                          Slide {num}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="audio-file" className="text-xs">Replacement Audio (.wav / .mp3)</Label>
                  <Input
                    id="audio-file"
                    type="file"
                    accept=".wav,.mp3,.ogg,.flac,.m4a"
                    className="h-9 text-xs cursor-pointer"
                    onChange={(e) => setAudioFile(e.target.files?.[0] || null)}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmittingAudio}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={!audioFile || isSubmittingAudio}>
                  {isSubmittingAudio ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1.5" /> Updating Audio...
                    </>
                  ) : (
                    <>
                      <Volume2 className="h-3.5 w-3.5 mr-1.5" /> Replace Slide Audio
                    </>
                  )}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
