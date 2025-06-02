// import React, { useState } from 'react';
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
// import { Badge } from "@/components/ui/badge";

// interface TranscriptSegment {
//   text: string;
//   start: number;
//   end: number;
//   start_formatted: string;
//   end_formatted: string;
//   confidence?: number;
// }

interface TranscriptViewerProps {
  transcript: string;
  // language: string;
  // segments_with_profanity: TranscriptSegment[];
  // all_segments: TranscriptSegment[];
  // full_transcript_available: boolean;
}

export function TranscriptViewer({
  transcript,
}: TranscriptViewerProps) {
  // const [activeTab, setActiveTab] = useState<string>(full_transcript_available ? "full" : "profanity");

  if (!transcript) {
    return (
      <Card className="w-full bg-muted/30">
        <CardHeader>
          <CardTitle>Transcript</CardTitle>
          <CardDescription>No transcript available</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  console.log("TranscriptViewer", transcript);
  return (
    <Card className="w-full bg-muted/30">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Transcript</span>
          
        </CardTitle>
      </CardHeader>
      <CardContent className="">
        {/* <Tabs defaultValue={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="full" disabled={!full_transcript_available}>
              Full Transcript
            </TabsTrigger>
            <TabsTrigger value="profanity">
              Profanity Only ({segments_with_profanity.length})
            </TabsTrigger>
          </TabsList>
          
          {full_transcript_available && (
            <TabsContent value="full" className="mt-4">
              <div className="space-y-4 max-h-96 overflow-y-auto p-2">
                {all_segments.map((segment, index) => (
                  <div 
                    key={`segment-${index}`} 
                    className={`p-3 rounded-md ${
                      segments_with_profanity.some(
                        p => p.start === segment.start && p.end === segment.end
                      ) 
                        ? "bg-red-500/10 border border-red-500/30" 
                        : "bg-muted/50"
                    }`}
                  >
                    <div className="flex justify-between items-center mb-1 text-xs text-muted-foreground">
                      <span>{segment.start_formatted} - {segment.end_formatted}</span>
                      {segments_with_profanity.some(
                        p => p.start === segment.start && p.end === segment.end
                      ) && (
                        <Badge variant="destructive" className="bg-red-500">
                          Profanity
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm">{segment.text}</p>
                  </div>
                ))}
              </div>
            </TabsContent>
          )}
          
          <TabsContent value="profanity" className="mt-4">
            {segments_with_profanity.length > 0 ? (
              <div className="space-y-4 max-h-96 overflow-y-auto p-2">
                {segments_with_profanity.map((segment, index) => (
                  <div 
                    key={`profanity-${index}`} 
                    className="p-3 rounded-md bg-red-500/10 border border-red-500/30"
                  >
                    <div className="flex justify-between items-center mb-1 text-xs text-muted-foreground">
                      <span>{segment.start_formatted} - {segment.end_formatted}</span>
                      {segment.confidence && (
                        <Badge variant="destructive" className="bg-red-500">
                          {(segment.confidence * 100).toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm">{segment.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center text-muted-foreground">
                No profanity detected in the transcript
              </div>
            )}
          </TabsContent>
        </Tabs> */}
        
        {/* Full transcript text (collapsible) */}
        <div className="">
          {/* <details className="group"> */}
            <div className="mt-2 rounded-lg bg-muted/30 p-4 text-sm max-h-60 overflow-y-auto">
              {transcript}
            </div>
          {/* </details> */}
        </div>
      </CardContent>
    </Card>
  );
}