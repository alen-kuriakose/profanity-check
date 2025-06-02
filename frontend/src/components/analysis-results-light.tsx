import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { VideoAnalysisResult } from '@/lib/api';
import { TranscriptViewer } from '@/components/transcript-viewer';
import { 
  AlertCircle, 
  CheckCircle, 
  Clock, 
  FileVideo, 
  Shield, 
  AlertTriangle, 
  Eye, 
  Flame, 
  MessageSquare,
  Download,
  Filter,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { log } from 'console';

interface AnalysisResultsProps {
  results: VideoAnalysisResult;
}

export function AnalysisResults({ results }: AnalysisResultsProps) {
  // Ensure all properties have default values if they're missing
  const content_rating = results.content_rating || 'safe';
  const flags = results.flags || [];
  
  // Create a default summary if it's missing or incomplete
  const defaultSummary = {
    content_id: results.content_id || '',
    filename: results.filename || '',
    total_frames_analyzed: 0,
    frames_with_inappropriate_content: 0,
    inappropriate_percentage: 0,
    nsfw: { frames_detected: 0, percentage: 0, max_confidence: 0 },
    violence: { frames_detected: 0, percentage: 0, max_confidence: 0 },
    profanity: { frames_detected: 0, percentage: 0, max_confidence: 0 },
    processing_time_seconds: 0,
    frames_per_second: 0
  };
  
  // Merge the actual summary with the default summary to ensure all properties exist
  const summary = {
    ...defaultSummary,
    ...(results.summary || {}),
    // Ensure nested objects are properly initialized
    nsfw: { ...defaultSummary.nsfw, ...(results.summary?.nsfw || {}) },
    violence: { ...defaultSummary.violence, ...(results.summary?.violence || {}) },
    profanity: { ...defaultSummary.profanity, ...(results.summary?.profanity || {}) }
  };
  
  const [showAllFrames, setShowAllFrames] = useState(false);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  
  // Function to handle sorting
  const handleSort = (column: string) => {
    if (sortColumn === column) {
      // Toggle direction if same column
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new column and default to descending
      setSortColumn(column);
      setSortDirection('desc');
    }
  };
  
  // Sort flags based on current sort settings
  const sortedFlags = [...flags].sort((a, b) => {
    if (!sortColumn) return 0;
    
    let comparison = 0;
    
    if (sortColumn === 'timestamp') {
      comparison = (a.timestamp || 0) - (b.timestamp || 0);
    } else if (sortColumn === 'confidence') {
      comparison = (a.confidence || 0) - (b.confidence || 0);
    }
    
    return sortDirection === 'asc' ? comparison : -comparison;
  });
  
  // Ensure detailed_results is an array and has all required properties
  const detailedResults = (results.detailed_results || []).map(frame => {
    // Calculate if frame has inappropriate content based on detection flags
    const hasInappropriateContent = 
      (frame.nsfw?.detected === true) || 
      (frame.violence?.detected === true) || 
      (frame.profanity?.detected === true);
    
    return {
      frame_number: frame.frame_number || 0,
      timestamp_seconds: frame.timestamp_seconds || 0,
      timestamp_formatted: frame.timestamp_formatted || '0:00',
      has_inappropriate_content: hasInappropriateContent, // Use calculated value instead of potentially null field
      nsfw: {
        detected: frame.nsfw?.detected || false,
        confidence: frame.nsfw?.confidence || 0
      },
      violence: {
        detected: frame.violence?.detected || false,
        confidence: frame.violence?.confidence || 0
      },
      profanity: {
        detected: frame.profanity?.detected || false,
        confidence: frame.profanity?.confidence || 0,
        text: frame.profanity?.text || ''
      }
    };
  });
  console.log('Detailed results:', detailedResults);
  
  // Filter detailed results to show only flagged frames or all frames
  const filteredDetailedResults = showAllFrames 
    ? detailedResults 
    : detailedResults.filter(frame => 
        frame.nsfw.detected || frame.violence.detected || frame.profanity.detected
      );
  
  // Sort detailed results
  const sortedDetailedResults = [...filteredDetailedResults].sort((a, b) => {
    if (!sortColumn) return 0;
    
    let comparison = 0;
    
    if (sortColumn === 'timestamp') {
      comparison = a.timestamp_seconds - b.timestamp_seconds;
    } else if (sortColumn === 'confidence') {
      // Get max confidence across all types
      const getMaxConfidence = (frame: any) => {
        return Math.max(
          frame.nsfw.detected ? frame.nsfw.confidence : 0,
          frame.violence.detected ? frame.violence.confidence : 0,
          frame.profanity.detected ? frame.profanity.confidence : 0
        );
      };
      
      comparison = getMaxConfidence(a) - getMaxConfidence(b);
    }
    
    return sortDirection === 'asc' ? comparison : -comparison;
  });
  
  // Function to export results as JSON
  const handleExportResults = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(results, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `analysis_${results.content_id}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };
  
  console.log("jdjfjd",results)

  return (
    <div className="space-y-8">
      {/* Summary Card */}
      <Card className="border-gray-200 shadow-md">
        <CardHeader className="pb-4">
          <CardTitle>Analysis Summary</CardTitle>
          <CardDescription>
            Overview of content analysis for {summary.filename}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Content Rating */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-lg bg-gray-50 border border-gray-200">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full ${
                content_rating === 'safe' ? 'bg-green-100 text-green-600' :
                content_rating === 'questionable' ? 'bg-yellow-100 text-yellow-600' :
                'bg-red-100 text-red-600'
              }`}>
                {content_rating === 'safe' ? (
                  <CheckCircle className="h-6 w-6" />
                ) : content_rating === 'questionable' ? (
                  <AlertTriangle className="h-6 w-6" />
                ) : (
                  <AlertCircle className="h-6 w-6" />
                )}
              </div>
              <div>
                <h3 className="font-medium text-gray-800">Content Rating</h3>
                <p className="text-sm text-gray-500">Based on automated analysis</p>
              </div>
            </div>
            <Badge className={`text-sm px-3 py-1 ${
              content_rating === 'safe' ? 'bg-green-100 text-green-700 border-green-200' :
              content_rating === 'questionable' ? 'bg-yellow-100 text-yellow-700 border-yellow-200' :
              'bg-red-100 text-red-700 border-red-200'
            }`}>
              {content_rating.charAt(0).toUpperCase() + content_rating.slice(1)}
            </Badge>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex justify-between items-start mb-2">
                <div className="text-sm font-medium text-gray-600">Processing Time</div>
                <Clock className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-800">{summary.processing_time_seconds.toFixed(1)}s</div>
              <div className="text-sm text-gray-500 mt-1">{summary.frames_per_second.toFixed(1)} frames/second</div>
            </div>
            
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex justify-between items-start mb-2">
                <div className="text-sm font-medium text-gray-600">Frames Analyzed</div>
                <FileVideo className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-800">{summary.total_frames_analyzed}</div>
              <div className="text-sm text-gray-500 mt-1">
                {summary.frames_with_inappropriate_content} flagged ({summary.inappropriate_percentage.toFixed(1)}%)
              </div>
            </div>
            
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <div className="flex justify-between items-start mb-2">
                <div className="text-sm font-medium text-gray-600">Content Issues</div>
                <Shield className="h-4 w-4 text-gray-500" />
              </div>
              <div className="text-2xl font-bold text-gray-800">{flags.length}</div>
              <div className="text-sm text-gray-500 mt-1">
                {flags.filter(f => f.type === 'explicit').length} explicit, {flags.filter(f => f.type === 'violent').length} violent, {flags.filter(f => f.type === 'profane').length} profane
              </div>
            </div>
          </div>

          {/* Content Type Analysis */}
          {/* <div className="space-y-6 p-4 rounded-lg bg-gray-50 border border-gray-200">
            <h3 className="text-lg font-medium text-gray-800 mb-4">Content Type Analysis</h3>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="h-4 w-4 text-red-600" />
                  <span className="font-medium text-gray-700">Explicit Content</span>
                </div>
                <span className="text-sm text-gray-600">
                  {summary.nsfw?.frames_detected || 0} frames ({(summary.nsfw?.percentage || 0).toFixed(1)}%)
                </span>
              </div>
              <div className="relative">
                <Progress 
                  value={summary.nsfw?.percentage || 0} 
                  className="h-3 bg-gray-200" 
                />
                {(summary.nsfw?.percentage || 0) > 0 && (
                  <div className="absolute right-0 top-0 transform translate-x-1/2 -translate-y-1/2 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                    {summary.nsfw?.max_confidence ? (Math.round(summary.nsfw?.max_confidence * 100)) + '%' : ''}
                  </div>
                )}
              </div>
            </div>
            
            <div className="space-y-2 mt-4">
              <div className="flex justify-between">
                <div className="flex items-center gap-2">
                  <Flame className="h-4 w-4 text-orange-600" />
                  <span className="font-medium text-gray-700">Violent Content</span>
                </div>
                <span className="text-sm text-gray-600">
                  {summary.violence?.frames_detected || 0} frames ({(summary.violence?.percentage || 0).toFixed(1)}%)
                </span>
              </div>
              <div className="relative">
                <Progress 
                  value={summary.violence?.percentage || 0} 
                  className="h-3 bg-gray-200" 
                />
                {(summary.violence?.percentage || 0) > 0 && (
                  <div className="absolute right-0 top-0 transform translate-x-1/2 -translate-y-1/2 bg-orange-500 text-white text-xs px-2 py-0.5 rounded-full">
                    {summary.violence?.max_confidence ? (Math.round(summary.violence?.max_confidence * 100)) + '%' : ''}
                  </div>
                )}
              </div>
            </div>
            
            <div className="space-y-2 mt-4">
              <div className="flex justify-between">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-purple-600" />
                  <span className="font-medium text-gray-700">Profane Content</span>
                </div>
                <span className="text-sm text-gray-600">
                  {summary.profanity?.frames_detected || 0} frames ({(summary.profanity?.percentage || 0).toFixed(1)}%)
                </span>
              </div>
              <div className="relative">
                <Progress 
                  value={summary.profanity?.percentage || 0} 
                  className="h-3 bg-gray-200" 
                />
                {(summary.profanity?.percentage || 0) > 0 && (
                  <div className="absolute right-0 top-0 transform translate-x-1/2 -translate-y-1/2 bg-purple-500 text-white text-xs px-2 py-0.5 rounded-full">
                    {summary.profanity?.max_confidence ? (Math.round(summary.profanity?.max_confidence * 100)) + '%' : ''}
                  </div>
                )}
              </div>
            </div>
          </div> */}
        </CardContent>
      </Card>

      {/* Detailed Analysis */}
      <Tabs defaultValue="flags" className="w-full">
        <TabsList className="bg-gray-100 border border-gray-200 mb-6">
          <TabsTrigger value="flags" className="data-[state=active]:bg-white">Content Flags</TabsTrigger>
          <TabsTrigger value="frames" className="data-[state=active]:bg-white">Frame Analysis</TabsTrigger>
          <TabsTrigger 
            value="transcript" 
            className="data-[state=active]:bg-white"
            disabled={!results.transcript && !(summary.profanity?.transcript_available)}
          >
            Transcript
          </TabsTrigger>
          <TabsTrigger 
            value="model-responses" 
            className="data-[state=active]:bg-white"
            disabled={!summary.model_responses || summary.model_responses.length === 0}
          >
            Model Responses
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="flags" className="space-y-4">
          <Card className="border-gray-200 shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div>
                <CardTitle>Content Flags</CardTitle>
                <CardDescription>
                  {flags.length} issues detected in the video
                </CardDescription>
              </div>
              
              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-8 gap-1"
                  onClick={handleExportResults}
                >
                  <Download className="h-3.5 w-3.5" />
                  Export
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              {flags.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader className="bg-gray-50">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="w-[120px]">Type</TableHead>
                        <TableHead className="w-[120px]">Timestamp</TableHead>
                        <TableHead className="w-[150px]">Confidence</TableHead>
                        <TableHead>Details</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedFlags.map((flag, index) => (
                        <TableRow key={index} className="hover:bg-gray-50">
                          <TableCell>
                            <Badge 
                              className={
                                flag.type === 'explicit' ? 'bg-red-100 text-red-700 border-red-200' : 
                                flag.type === 'violent' ? 'bg-orange-100 text-orange-700 border-orange-200' : 
                                'bg-purple-100 text-purple-700 border-purple-200'
                              }
                            >
                              {flag.type}
                            </Badge>
                          </TableCell>
                          <TableCell>{flag.timestamp_formatted || `${Math.floor(flag.timestamp / 60)}:${Math.floor(flag.timestamp % 60).toString().padStart(2, '0')}`}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Progress value={flag.confidence * 100} className="h-2 w-24 bg-gray-200" />
                              <span>{Math.round(flag.confidence * 100)}%</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            {flag.type === 'profane' && flag.text ? (
                              <div className="flex flex-col">
                                <span>"{flag.text}"</span>
                                {/* <span className="text-xs text-gray-500">Frame {flag.frame_number}</span> */}
                              </div>
                            ) : (
                              <div className="flex flex-col">
                                <span>Frame {flag.frame_number}</span>
                                {flag.model_response && (
                                  <button 
                                    className="text-xs text-blue-600 hover:text-blue-800 mt-1"
                                    onClick={() => {
                                      // Find the tab trigger for model responses and click it
                                      const modelResponsesTab = document.querySelector('[value="model-responses"]');
                                      if (modelResponsesTab) {
                                        (modelResponsesTab as HTMLElement).click();
                                      }
                                    }}
                                  >
                                    View model response
                                  </button>
                                )}
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <CheckCircle className="h-12 w-12 mx-auto text-green-500 mb-4" />
                  <h3 className="text-xl font-medium text-gray-800 mb-2">No Content Issues Detected</h3>
                  <p className="text-gray-500">This video appears to be safe based on our analysis.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="frames" className="space-y-4">
          <Card className="border-gray-200 shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div>
                <CardTitle>Frame-by-Frame Analysis</CardTitle>
                <CardDescription>
                  Detailed analysis of {detailedResults.length} video frames
                </CardDescription>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex items-center gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className={`h-8 gap-1 ${showAllFrames ? 'bg-gray-100' : ''}`}
                    onClick={() => setShowAllFrames(!showAllFrames)}
                  >
                    <Filter className="h-3.5 w-3.5" />
                    {showAllFrames ? 'Show Flagged Only' : 'Show All Frames'}
                  </Button>
                </div>
                
                {filteredDetailedResults.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500">Sort by:</span>
                    <div className="flex gap-2">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={`h-8 px-2 ${sortColumn === 'timestamp' ? 'bg-gray-100' : ''}`}
                        onClick={() => handleSort('timestamp')}
                      >
                        Time
                        {sortColumn === 'timestamp' && (
                          sortDirection === 'asc' ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />
                        )}
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={`h-8 px-2 ${sortColumn === 'confidence' ? 'bg-gray-100' : ''}`}
                        onClick={() => handleSort('confidence')}
                      >
                        Confidence
                        {sortColumn === 'confidence' && (
                          sortDirection === 'asc' ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />
                        )}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              {filteredDetailedResults.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader className="bg-gray-50">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="w-[100px]">Frame</TableHead>
                        <TableHead className="w-[100px]">Time</TableHead>
                        <TableHead className="w-[120px]">NSFW</TableHead>
                        <TableHead className="w-[120px]">Violence</TableHead>
                        <TableHead>Profanity</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedDetailedResults.map((frame, index) => (
                        <TableRow key={index} className={frame.has_inappropriate_content ? "bg-gray-50 hover:bg-gray-100" : "hover:bg-gray-50"}>
                          <TableCell>{frame.frame_number}</TableCell>
                          <TableCell>{frame.timestamp_formatted}</TableCell>
                          <TableCell>
                            {frame.nsfw.detected ? (
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-red-500"></div>
                                <span className="text-red-600">{Math.round(frame.nsfw.confidence * 100)}%</span>
                              </div>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {frame.violence.detected ? (
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-orange-500"></div>
                                <span className="text-orange-600">{Math.round(frame.violence.confidence * 100)}%</span>
                              </div>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {frame.profanity.detected ? (
                              <div className="flex items-start gap-2">
                                <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5"></div>
                                <div className="flex flex-col">
                                  <span className="text-purple-600">
                                    {Math.round(frame.profanity.confidence * 100)}%
                                  </span>
                                  {frame.profanity.text && (
                                    <span className="text-sm text-gray-600 mt-0.5">
                                      "{frame.profanity.text}"
                                    </span>
                                  )}
                                </div>
                              </div>
                            ) : (
                              <span className="text-gray-400">-</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <FileVideo className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                  <h3 className="text-xl font-medium text-gray-800 mb-2">No Frame Data Available</h3>
                  <p className="text-gray-500">No frame analysis data is available for this video.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="transcript" className="space-y-4">
          {results?.summary?.transcript ? (
            <TranscriptViewer
              transcript={results?.summary.transcript}
              // language={results.transcript.language || "en"}
              // segments_with_profanity={results.transcript.segments_with_profanity || []}
              // all_segments={results.transcript.all_segments || []}
              // full_transcript_available={results.full_transcript_available || false}
            />
          ) : (
            <Card className="border-gray-200 shadow-md">
              <CardHeader>
                <CardTitle>Transcript</CardTitle>
                <CardDescription>
                  No transcript available for this video
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <MessageSquare className="h-12 w-12 text-gray-300 mb-4" />
                  <p className="text-gray-500">No transcript data is available for this video.</p>
                  {summary.profanity?.has_profanity && !summary.profanity?.transcript_available && (
                    <p className="text-sm text-gray-400 mt-2">
                      Profanity was detected but no transcript was generated
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        
        <TabsContent value="model-responses" className="space-y-4">
          <Card className="border-gray-200 shadow-md">
            <CardHeader>
              <CardTitle>AI Model Responses</CardTitle>
              <CardDescription>
                Raw responses from the SmolVLM model for each analyzed frame
              </CardDescription>
            </CardHeader>
            <CardContent>
              {summary.model_responses && summary.model_responses.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader className="bg-gray-50">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="w-[100px]">Frame</TableHead>
                        <TableHead className="w-[150px]">Result</TableHead>
                        <TableHead>Model Response</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {summary.model_responses.map((response, index) => (
                        <TableRow key={index} className={response.parsed_json?.inappropriate === "YES" ? "bg-gray-50 hover:bg-gray-100" : "hover:bg-gray-50"}>
                          <TableCell>{response.frame_number}</TableCell>
                          <TableCell>
                            {response.parsed_json?.inappropriate === "YES" ? (
                              <Badge className="bg-red-100 text-red-700 border-red-200">
                                Inappropriate
                              </Badge>
                            ) : (
                              <Badge className="bg-green-100 text-green-700 border-green-200">
                                Safe
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="max-h-32 overflow-y-auto p-2 bg-gray-50 rounded border border-gray-200 text-sm font-mono">
                              {response.raw_response}
                            </div>
                            {response.parsed_json?.inappropriate === "YES" && (
                              <div className="mt-2">
                                <span className="font-semibold">Category:</span> {response.parsed_json.category || "Unknown"}<br />
                                <span className="font-semibold">Description:</span> {response.parsed_json.description || "No description"}
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <FileVideo className="h-12 w-12 text-gray-300 mb-4" />
                  <p className="text-gray-500">No model response data is available for this video.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}