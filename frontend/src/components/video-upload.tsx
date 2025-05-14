import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import {
  videoAnalysisApi,
  asyncVideoAnalysisApi,
  VideoAnalysisResult,
} from "@/lib/api";
import {
  UploadIcon,
  Loader2,
  Clock,
  CheckCircle,
  FileVideo,
  AlertTriangle,
  Info,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

interface VideoUploadProps {
  onAnalysisComplete: (result: VideoAnalysisResult) => void;
}

export function VideoUpload({ onAnalysisComplete }: VideoUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [contentId, setContentId] = useState("");
  const [frameInterval, setFrameInterval] = useState(30);
  const [checkNsfw, setCheckNsfw] = useState(true);
  const [checkViolence, setCheckViolence] = useState(true);
  const [checkProfanity, setCheckProfanity] = useState(true);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.5);
  const [isUploading, setIsUploading] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"sync" | "async">("sync");
  const [asyncStatus, setAsyncStatus] = useState<string | null>(null);
  const [asyncStatusCheckInterval, setAsyncStatusCheckInterval] =
    useState<NodeJS.Timeout | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0]);
        // Generate a default content ID based on the file name
        if (!contentId) {
          const fileName = acceptedFiles[0].name.split(".")[0];
          setContentId(`${fileName}-${Date.now()}`);
        }
      }
    },
    [contentId]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "video/*": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
    },
    maxFiles: 1,
  });

  // Clean up interval on component unmount
  React.useEffect(() => {
    return () => {
      if (asyncStatusCheckInterval) {
        clearInterval(asyncStatusCheckInterval);
      }
    };
  }, [asyncStatusCheckInterval]);

  const checkAsyncStatus = useCallback(
    async (id: string) => {
      try {
        const statusResponse = await asyncVideoAnalysisApi.checkStatus(id);
        setAsyncStatus(statusResponse.status);

        if (statusResponse.status === "completed") {
          if (asyncStatusCheckInterval) {
            clearInterval(asyncStatusCheckInterval);
            setAsyncStatusCheckInterval(null);
          }

          // Get the results
          const results = await asyncVideoAnalysisApi.getResults(id, true);

          // Save video to list
          await asyncVideoAnalysisApi.addVideoToList({
            contentId: results.content_id,
            filename: results.filename,
            uploadDate: new Date().toISOString(),
            status: "completed",
            contentRating: results.content_rating,
            flaggedFrames: results.summary?.frames_with_inappropriate_content,
            totalFrames: results.summary?.total_frames_analyzed,
          });

          toast.success("Video analysis completed successfully");
          onAnalysisComplete(results);
          // We don't need to set isUploading to false here as it's already set after upload
        } else if (statusResponse.status === "failed") {
          if (asyncStatusCheckInterval) {
            clearInterval(asyncStatusCheckInterval);
            setAsyncStatusCheckInterval(null);
          }

          toast.error("Video analysis failed");
          // We don't need to set isUploading to false here as it's already set after upload
        } else if (statusResponse.status === "queued") {
          // Update the status for queued videos
          setAsyncStatus("queued");
        }
      } catch (error) {
        console.error("Error checking status:", error);
        if (asyncStatusCheckInterval) {
          clearInterval(asyncStatusCheckInterval);
          setAsyncStatusCheckInterval(null);
        }
        toast.error("Failed to check analysis status");
        // We don't need to set isUploading to false here as it's already set after upload
      }
    },
    [asyncStatusCheckInterval, onAnalysisComplete]
  );

  const handleSyncAnalysis = async () => {
    if (!file) {
      toast.error("Please select a video file to upload");
      return;
    }

    if (!contentId) {
      toast.error("Please enter a content ID");
      return;
    }

    setIsUploading(true);

    try {
      // Simulate upload progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      let result;

      // If only profanity check is enabled, use the dedicated profanity endpoint
      if (checkProfanity && !checkNsfw && !checkViolence) {
        console.log("Using dedicated profanity check endpoint");
        result = await videoAnalysisApi.checkProfanity(file, {
          contentId: contentId,
        });

        // Ensure the result has the expected structure
        if (!result.detailed_results && result.timestamp_results) {
          result.detailed_results = result.timestamp_results.map(
            (item: any) => ({
              frame_number: item.frame_number || 0,
              timestamp_seconds: item.timestamp || 0,
              timestamp_formatted: item.timestamp_formatted || "0:00",
              has_inappropriate_content: item.has_profanity || false,
              nsfw: { detected: false, confidence: 0 },
              violence: { detected: false, confidence: 0 },
              profanity: {
                detected: item.has_profanity || false,
                confidence: item.confidence || 0,
                text: item.text || "",
              },
            })
          );
        }
      } 
      // If only NSFW check is enabled, use the dedicated NSFW endpoint
      else if (checkNsfw && !checkProfanity && !checkViolence) {
        console.log("Using dedicated NSFW check endpoint");
        const nsfwResult = await videoAnalysisApi.checkNsfw(file, {
          frameInterval,
          confidenceThreshold,
          resizeMaxDimension: 480, // Default value
        });
        
        // Format the result to match the expected structure
        result = {
          content_id: contentId,
          filename: file.name,
          status: "completed",
          content_rating: nsfwResult.result === 200 ? "safe" : "explicit",
          summary: {
            content_id: contentId,
            filename: file.name,
            total_frames_analyzed: 0,
            frames_with_inappropriate_content: 0,
            inappropriate_percentage: 0,
            nsfw: {
              frames_detected: 0,
              percentage: 0,
              max_confidence: 0,
            },
            violence: {
              frames_detected: 0,
              percentage: 0,
              max_confidence: 0,
            },
            profanity: {
              frames_detected: 0,
              percentage: 0,
              max_confidence: 0,
            },
            processing_time_seconds: 0,
            frames_per_second: 0,
          },
          detailed_results: []
        };
      } 
      else {
        // Use the comprehensive analysis endpoint
        result = await videoAnalysisApi.analyzeVideo(file, contentId, {
          frameInterval,
          checkNsfw,
          checkViolence,
          checkProfanity,
          confidenceThreshold,
        });
      }

      clearInterval(progressInterval);
      setUploadProgress(100);

      // Save video to list
      await asyncVideoAnalysisApi.addVideoToList({
        contentId: result.content_id,
        filename: result.filename,
        uploadDate: new Date().toISOString(),
        status: "completed",
        contentRating: result.content_rating,
        flaggedFrames: result.summary.frames_with_inappropriate_content,
        totalFrames: result.summary.total_frames_analyzed,
      });

      toast.success("Video analysis completed successfully");
      onAnalysisComplete(result);
    } catch (error) {
      console.error("Error analyzing video:", error);
      toast.error("Failed to analyze video. Please try again.");
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleAsyncAnalysis = async () => {
    if (!file) {
      toast.error("Please select a video file to upload");
      return;
    }

    if (!contentId) {
      toast.error("Please enter a content ID");
      return;
    }

    setIsUploading(true);
    setAsyncStatus("uploading");

    try {
      // Simulate upload progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 5;
        });
      }, 300);

      // Upload the video and start analysis
      const uploadResponse = await asyncVideoAnalysisApi.uploadVideo(
        file,
        contentId,
        true
      );

      clearInterval(progressInterval);
      setUploadProgress(100);

      // Save video to list with pending status
      await asyncVideoAnalysisApi.addVideoToList({
        contentId: uploadResponse.content_id,
        filename: uploadResponse.filename,
        uploadDate: new Date().toISOString(),
        status: uploadResponse.status || "processing",
      });

      // Reset form for next upload
      setFile(null);
      setContentId("");
      setUploadProgress(0);
      
      // Enable the upload button after successful upload
      setIsUploading(false);
      
      toast.success("Video uploaded successfully, analysis in progress");
      setAsyncStatus(uploadResponse.status || "processing");

      // Set up interval to check status
      const interval = setInterval(() => checkAsyncStatus(contentId), 5000);
      setAsyncStatusCheckInterval(interval);
    } catch (error) {
      console.error("Error uploading video:", error);
      toast.error("Failed to upload video. Please try again.");
      setIsUploading(false);
      setAsyncStatus(null);
      setUploadProgress(0);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (analysisMode === "sync") {
      await handleSyncAnalysis();
    } else {
      await handleAsyncAnalysis();
    }
  };

  return (
    <Card className="w-full mx-auto shadow-lg border-2">
      <CardHeader className="bg-muted/30">
        <CardTitle className="flex items-center gap-2">
          <FileVideo className="h-5 w-5 text-primary" />
          Video Analysis
        </CardTitle>
        <CardDescription>
          Upload a video to analyze it for inappropriate content
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-6  ">
        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-6">
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="content-id" className="text-base font-medium">
                Content ID
              </Label>
              <Input
                id="content-id"
                value={contentId}
                onChange={(e) => setContentId(e.target.value)}
                placeholder="Enter a unique identifier for this content"
                className="h-10"
                required
              />
              <p className="text-xs text-muted-foreground">
                This ID will be used to reference your analysis results
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-base font-medium">Upload Video</Label>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                  isDragActive
                    ? "border-primary bg-primary/10"
                    : "border-border"
                } ${file ? "bg-muted/30" : "hover:bg-muted/20"}`}
              >
                <input {...getInputProps()} />
                {file ? (
                  <div className="space-y-3">
                    <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                      <FileVideo className="h-8 w-8 text-primary" />
                    </div>
                    <div>
                      <p className="text-base font-medium">{file.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {(file.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    </div>
                    <Badge variant="outline" className="bg-primary/5">
                      Video Selected
                    </Badge>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="bg-muted w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                      <UploadIcon className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-base font-medium">
                        Drag & drop a video file here
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Or click to browse your files
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Supports MP4, MOV, AVI, MKV, WEBM
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
          <div>
            <Tabs
              defaultValue="sync"
              onValueChange={(value) =>
                setAnalysisMode(value as "sync" | "async")
              }
              className="mt-8"
            >
              <TabsList className="grid w-full grid-cols-2 h-fit">
                <TabsTrigger value="sync" className="rounded-md ">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <span>Synchronous</span>
                  </div>
                </TabsTrigger>
                <TabsTrigger value="async" className="rounded-md py-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4" />
                    <span>Asynchronous</span>
                  </div>
                </TabsTrigger>
              </TabsList>

              <TabsContent value="sync" className="space-y-6 pt-10">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label
                      htmlFor="frame-interval"
                      className="text-sm font-medium"
                    >
                      Frame Interval
                    </Label>
                    <Input
                      id="frame-interval"
                      type="number"
                      min="1"
                      max="100"
                      value={frameInterval}
                      onChange={(e) =>
                        setFrameInterval(parseInt(e.target.value))
                      }
                      className="h-9"
                    />
                    <p className="text-xs text-muted-foreground">
                      Process every Nth frame (higher = faster but less
                      accurate)
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label
                      htmlFor="confidence-threshold"
                      className="text-sm font-medium"
                    >
                      Confidence Threshold
                    </Label>
                    <Input
                      id="confidence-threshold"
                      type="number"
                      min="0"
                      max="1"
                      step="0.1"
                      value={confidenceThreshold}
                      onChange={(e) =>
                        setConfidenceThreshold(parseFloat(e.target.value))
                      }
                      className="h-9"
                    />
                    <p className="text-xs text-muted-foreground">
                      Minimum confidence level (0-1) for detection
                    </p>
                  </div>
                </div>

                <div className="space-y-3">
                  <Label className="text-sm font-medium">
                    Analysis Options
                  </Label>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="flex items-center space-x-2 bg-muted/30 p-3 rounded-md">
                      <Checkbox
                        id="check-nsfw"
                        checked={checkNsfw}
                        onCheckedChange={(checked) =>
                          setCheckNsfw(checked === true)
                        }
                        className="data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                      />
                      <Label
                        htmlFor="check-nsfw"
                        className="cursor-pointer text-sm"
                      >
                        NSFW Content
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2 bg-muted/30 p-3 rounded-md">
                      <Checkbox
                        id="check-violence"
                        checked={checkViolence}
                        onCheckedChange={(checked) =>
                          setCheckViolence(checked === true)
                        }
                        className="data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                      />
                      <Label
                        htmlFor="check-violence"
                        className="cursor-pointer text-sm"
                      >
                        Violence
                      </Label>
                    </div>

                    <div className="flex items-center space-x-2 bg-muted/30 p-3 rounded-md">
                      <Checkbox
                        id="check-profanity"
                        checked={checkProfanity}
                        onCheckedChange={(checked) =>
                          setCheckProfanity(checked === true)
                        }
                        className="data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                      />
                      <Label
                        htmlFor="check-profanity"
                        className="cursor-pointer text-sm"
                      >
                        Profanity
                      </Label>
                    </div>
                  </div>
                </div>

                <div className="bg-blue-50 border border-blue-100 p-4 rounded-md flex items-start gap-3">
                  <Info className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm text-blue-700 font-medium">
                      Synchronous Analysis
                    </p>
                    <p className="text-xs text-blue-600 mt-1">
                      The video will be analyzed immediately and results will be
                      returned when complete. Best for smaller videos (under
                      50MB).
                    </p>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="async" className="space-y-6 pt-4">
                <div className="bg-amber-50 border border-amber-100 p-4 rounded-md flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm text-amber-700 font-medium">
                      Asynchronous Analysis
                    </p>
                    <p className="text-xs text-amber-600 mt-1">
                      The video will be uploaded and processed in the
                      background. This is recommended for larger videos. You'll
                      be redirected to the results page when the analysis is
                      complete.
                    </p>
                  </div>
                </div>

                {asyncStatus && (
                  <div
                    className={`p-4 rounded-md ${
                      asyncStatus === "completed"
                        ? "bg-green-50 border border-green-100 text-green-700"
                        : asyncStatus === "failed"
                        ? "bg-red-50 border border-red-100 text-red-700"
                        : "bg-blue-50 border border-blue-100 text-blue-700"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {asyncStatus === "uploading" && (
                        <UploadIcon className="h-5 w-5 animate-pulse" />
                      )}
                      {(asyncStatus === "processing" || asyncStatus === "queued") && (
                        <Clock className="h-5 w-5 animate-pulse" />
                      )}
                      {asyncStatus === "completed" && (
                        <CheckCircle className="h-5 w-5" />
                      )}
                      <p className="text-sm font-medium capitalize">
                        {asyncStatus === "queued" ? "Queued for processing" : asyncStatus}
                      </p>
                    </div>
                  </div>
                )}
              </TabsContent>
            </Tabs>
            {isUploading && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>
                    {uploadProgress < 100 ? "Uploading..." : "Processing..."}
                  </span>
                  <span>{uploadProgress}%</span>
                </div>
                <Progress value={uploadProgress} className="h-2" />
              </div>
            )}
            <CardFooter className="flex justify-end px-0 pt-6 pb-0">
              <Button
                type="submit"
                disabled={isUploading || !file}
                className="px-8 py-2 h-11"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {analysisMode === "sync"
                      ? "Analyzing..."
                      : "Uploading..."}
                  </>
                ) : analysisMode === "sync" ? (
                  "Analyze Video"
                ) : (
                  "Upload & Analyze"
                )}
              </Button>
            </CardFooter>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
