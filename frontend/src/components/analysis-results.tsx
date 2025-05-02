import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { VideoAnalysisResult } from '@/lib/api';
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

  // Helper function to get color based on content rating
  const getRatingColor = (rating: string) => {
    switch (rating) {
      case 'safe':
        return 'bg-green-500';
      case 'questionable':
        return 'bg-yellow-500';
      case 'explicit':
        return 'bg-red-500';
      case 'violent':
        return 'bg-orange-500';
      case 'profane':
        return 'bg-purple-500';
      default:
        return 'bg-gray-500';
    }
  };

  // Helper function to format time
  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  // Function to handle sorting
  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  // Sort flags based on current sort settings
  const sortedFlags = [...flags].sort((a, b) => {
    if (!sortColumn) return 0;
    
    let comparison = 0;
    if (sortColumn === 'type') {
      comparison = a.type.localeCompare(b.type);
    } else if (sortColumn === 'timestamp') {
      comparison = a.timestamp - b.timestamp;
    } else if (sortColumn === 'confidence') {
      comparison = a.confidence - b.confidence;
    }
    
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  // Ensure detailed_results is an array and has all required properties
  const detailedResults = (results.detailed_results || []).map(frame => ({
    frame_number: frame.frame_number || 0,
    timestamp_seconds: frame.timestamp_seconds || 0,
    timestamp_formatted: frame.timestamp_formatted || '0:00',
    has_inappropriate_content: frame.has_inappropriate_content || false,
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
  }));
  
  // Filter detailed results to show only flagged frames or all frames
  const filteredDetailedResults = showAllFrames 
    ? detailedResults 
    : detailedResults.filter(frame => frame.has_inappropriate_content);

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

  return (
    <div className="space-y-8">
      <Card className="shadow-xl    overflow-hidden">
        <CardHeader className=" border-b">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <CardTitle className="flex items-center gap-2 text-2xl">
                <FileVideo className="h-6 w-6 text-blue-400" />
                <span className="text-zinc-800">Analysis Results</span>
                <Badge 
                  className={`${getRatingColor(content_rating)} text-white ml-2 px-3 py-1`}
                >
                  {content_rating.toUpperCase()}
                </Badge>
              </CardTitle>
              <CardDescription className="mt-2 text-zinc-400">
                {results.filename} <span className="text-zinc-500 text-xs">(ID: {results.content_id})</span>
              </CardDescription>
            </div>
            <Button 
              variant="outline" 
              size="sm" 
              className="flex items-center gap-1 self-end border-zinc-700  hover:bg-zinc-800 text-zinc-800 hover:text-zinc-200 "
              onClick={handleExportResults}
            >
              <Download className="h-4 w-4" />
              Export Results
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-8 bg-zinc-900">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="space-y-8">
              <div>
                <h3 className="text-lg font-medium mb-5 text-zinc-200 flex items-center gap-2">
                  <Shield className="h-5 w-5 text-blue-400" />
                  Content Detection Summary
                </h3>
                <div className="space-y-6">
                  <div className="bg-zinc-800/50 p-4 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Eye className="h-5 w-5 text-red-400" />
                        <span className="text-sm font-medium text-zinc-200">NSFW Content</span>
                      </div>
                      <span className="text-sm font-medium text-zinc-300">
                        {summary.nsfw?.frames_detected || 0} frames ({(summary.nsfw?.percentage || 0).toFixed(1)}%)
                      </span>
                    </div>
                    <div className="relative">
                      <Progress 
                        value={summary.nsfw?.percentage || 0} 
                        className="h-3 bg-zinc-700" 
                        indicatorClassName="bg-gradient-to-r from-red-500 to-red-600"
                      />
                      {(summary.nsfw?.percentage || 0) > 0 && (
                        <div className="absolute right-0 top-0 transform translate-x-1/2 -translate-y-1/2 bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                          {summary.nsfw?.max_confidence ? (Math.round(summary.nsfw?.max_confidence * 100)) + '%' : ''}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="bg-zinc-800/50 p-4 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Flame className="h-5 w-5 text-orange-400" />
                        <span className="text-sm font-medium text-zinc-200">Violent Content</span>
                      </div>
                      <span className="text-sm font-medium text-zinc-300">
                        {summary.violence?.frames_detected || 0} frames ({(summary.violence?.percentage || 0).toFixed(1)}%)
                      </span>
                    </div>
                    <div className="relative">
                      <Progress 
                        value={summary.violence?.percentage || 0} 
                        className="h-3 bg-zinc-700" 
                        indicatorClassName="bg-gradient-to-r from-orange-500 to-orange-600"
                      />
                      {(summary.violence?.percentage || 0) > 0 && (
                        <div className="absolute right-0 top-0 transform translate-x-1/2 -translate-y-1/2 bg-orange-500 text-white text-xs px-2 py-0.5 rounded-full">
                          {summary.violence?.max_confidence ? (Math.round(summary.violence?.max_confidence * 100)) + '%' : ''}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="bg-zinc-800/50 p-4 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="h-5 w-5 text-purple-400" />
                        <span className="text-sm font-medium text-zinc-200">Profanity</span>
                      </div>
                      <span className="text-sm font-medium text-zinc-300">
                        {summary.profanity?.frames_detected || 0} frames ({(summary.profanity?.percentage || 0).toFixed(1)}%)
                      </span>
                    </div>
                    <div className="relative">
                      <Progress 
                        value={summary.profanity?.percentage || 0} 
                        className="h-3 bg-zinc-700" 
                        indicatorClassName="bg-gradient-to-r from-purple-500 to-purple-600"
                      />
                      {(summary.profanity?.percentage || 0) > 0 && (
                        <div className="absolute right-0 top-0 transform translate-x-1/2 -translate-y-1/2 bg-purple-500 text-white text-xs px-2 py-0.5 rounded-full">
                          {summary.profanity?.max_confidence ? (Math.round(summary.profanity?.max_confidence * 100)) + '%' : ''}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              
              <div className={`${content_rating === 'safe' ? 'bg-green-900/20 border-green-800/30' : 'bg-amber-900/20 border-amber-800/30'} p-5 rounded-xl border`}>
                <h3 className="text-base font-medium mb-3 text-zinc-200">Analysis Verdict</h3>
                <div className="flex items-start gap-3">
                  {content_rating === 'safe' ? (
                    <>
                      <Shield className="h-6 w-6 text-green-400 mt-0.5" />
                      <p className="text-zinc-300">
                        This content appears to be <span className="font-medium text-green-400">safe</span> for general viewing.
                        No inappropriate content was detected above the confidence threshold.
                      </p>
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="h-6 w-6 text-amber-400 mt-0.5" />
                      <p className="text-zinc-300">
                        This content has been flagged as <span className="font-medium text-amber-400">{content_rating}</span>.
                        {flags.length > 0 && ` ${flags.length} instances of inappropriate content were detected.`}
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-5">
              <div className="bg-blue-900/20 border border-blue-800/30 rounded-xl p-5 flex flex-col items-center justify-center">
                <div className="text-4xl font-bold text-blue-400">{summary.total_frames_analyzed || 0}</div>
                <div className="text-sm text-zinc-400 text-center mt-2">Frames Analyzed</div>
              </div>
              
              <div className={`${(summary.frames_with_inappropriate_content || 0) > 0 ? 'bg-red-900/20 border-red-800/30' : 'bg-green-900/20 border-green-800/30'} rounded-xl p-5 flex flex-col items-center justify-center border`}>
                <div className={`text-4xl font-bold ${(summary.frames_with_inappropriate_content || 0) > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {summary.frames_with_inappropriate_content || 0}
                </div>
                <div className="text-sm text-zinc-400 text-center mt-2">Flagged Frames</div>
              </div>
              
              <div className="bg-zinc-800/50 rounded-xl p-5 flex flex-col items-center justify-center">
                <div className="text-4xl font-bold text-zinc-200">{(summary.processing_time_seconds || 0).toFixed(1)}s</div>
                <div className="text-sm text-zinc-400 text-center mt-2">Processing Time</div>
              </div>
              
              <div className="bg-zinc-800/50 rounded-xl p-5 flex flex-col items-center justify-center">
                <div className="text-4xl font-bold text-zinc-200">{(summary.frames_per_second || 0).toFixed(1)}</div>
                <div className="text-sm text-zinc-400 text-center mt-2">Frames/Second</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      <Tabs defaultValue="flags" className="mt-8">
        <TabsList className="grid w-full grid-cols-3 p-1 bg-zinc-800/50 border border-zinc-700">
          <TabsTrigger value="flags" className="rounded-md py-2 data-[state=active]:bg-zinc-700 data-[state=active]:text-zinc-100">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              <span>Content Flags</span>
              {flags.length > 0 && (
                <Badge variant="secondary" className="ml-1 bg-red-500/20 text-red-300 border-red-500/30">{flags.length}</Badge>
              )}
            </div>
          </TabsTrigger>
          <TabsTrigger value="frames" className="rounded-md py-2 data-[state=active]:bg-zinc-700 data-[state=active]:text-zinc-100">
            <div className="flex items-center gap-2">
              <FileVideo className="h-4 w-4" />
              <span>Frame Details</span>
            </div>
          </TabsTrigger>
          <TabsTrigger value="timeline" className="rounded-md py-2 data-[state=active]:bg-zinc-700 data-[state=active]:text-zinc-100">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <span>Timeline</span>
            </div>
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="flags" className="mt-6">
          <Card className="shadow-xl border  bg-zinc-900">
            <CardHeader className="pb-0 border-b ">
              <div className="flex justify-between items-center">
                <CardTitle className="text-lg text-zinc-100 flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-400" />
                  Content Flags
                </CardTitle>
                {flags.length > 0 && (
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-zinc-400" />
                    <span className="text-sm text-zinc-400">Sort by:</span>
                    <div className="flex gap-2">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={`h-8 px-2 text-zinc-300 hover:bg-zinc-800 ${sortColumn === 'timestamp' ? 'bg-zinc-800' : ''}`}
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
                        className={`h-8 px-2 text-zinc-300 hover:bg-zinc-800 ${sortColumn === 'confidence' ? 'bg-zinc-800' : ''}`}
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
            <CardContent className="pt-6">
              {flags.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader className="bg-zinc-800/50">
                      <TableRow className="border-zinc-700 hover:bg-transparent">
                        <TableHead className="w-[120px] text-zinc-300">Type</TableHead>
                        <TableHead className="w-[120px] text-zinc-300">Timestamp</TableHead>
                        <TableHead className="w-[150px] text-zinc-300">Confidence</TableHead>
                        <TableHead className="text-zinc-300">Details</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedFlags.map((flag, index) => (
                        <TableRow key={index} className=" hover:bg-zinc-800/50">
                          <TableCell>
                            <Badge 
                              className={
                                flag.type === 'explicit' ? 'bg-gradient-to-r from-red-500 to-red-600 text-white border-0' : 
                                flag.type === 'violent' ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white border-0' : 
                                'bg-gradient-to-r from-purple-500 to-purple-600 text-white border-0'
                              }
                            >
                              {flag.type === 'explicit' && <Eye className="h-3 w-3 mr-1" />}
                              {flag.type === 'violent' && <Flame className="h-3 w-3 mr-1" />}
                              {flag.type === 'profane' && <MessageSquare className="h-3 w-3 mr-1" />}
                              {flag.type}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-zinc-300 font-mono">{formatTime(flag.timestamp)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-2 bg-zinc-700 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full ${
                                    flag.type === 'explicit' ? 'bg-red-500' : 
                                    flag.type === 'violent' ? 'bg-orange-500' : 
                                    'bg-purple-500'
                                  }`}
                                  style={{ width: `${Math.round(flag.confidence * 100)}%` }}
                                ></div>
                              </div>
                              <span className="text-zinc-300">{Math.round(flag.confidence * 100)}%</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm">
                            {flag.text ? (
                              <div className="bg-zinc-800 p-3 rounded-md text-zinc-300 border border-zinc-700">
                                "{flag.text}"
                              </div>
                            ) : (
                              <span className="text-zinc-500">-</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="bg-green-900/20 rounded-full p-6 mb-4 border border-green-800/30">
                    <CheckCircle className="h-16 w-16 text-green-400" />
                  </div>
                  <h3 className="text-xl font-medium text-green-400">No content flags detected</h3>
                  <p className="text-zinc-400 max-w-md mt-2">
                    This video appears to be safe with no inappropriate content detected above the confidence threshold.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="frames" className="mt-6">
          <Card className="shadow-xl border  bg-zinc-900">
            <CardHeader className="pb-0 border-b ">
              <div className="flex justify-between items-center">
                <CardTitle className="text-lg text-zinc-100 flex items-center gap-2">
                  <FileVideo className="h-5 w-5 text-blue-400" />
                  Frame Analysis
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => setShowAllFrames(!showAllFrames)}
                    className="border-zinc-700 bg-zinc-800/50 hover:bg-zinc-800 text-zinc-200"
                  >
                    {showAllFrames ? 'Show Flagged Only' : 'Show All Frames'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              {detailedResults.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader className="bg-zinc-800/50">
                      <TableRow className="border-zinc-700 hover:bg-transparent">
                        <TableHead className="w-[80px] text-zinc-300">Frame</TableHead>
                        <TableHead className="w-[100px] text-zinc-300">Timestamp</TableHead>
                        <TableHead className="w-[120px] text-zinc-300">NSFW</TableHead>
                        <TableHead className="w-[120px] text-zinc-300">Violence</TableHead>
                        <TableHead className="text-zinc-300">Profanity</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredDetailedResults.map((frame) => (
                        <TableRow 
                          key={frame.frame_number} 
                          className={`hover:bg-muted/30 ${frame.has_inappropriate_content ? 'bg-red-50/30' : ''}`}
                        >
                          <TableCell className="font-mono">{frame.frame_number}</TableCell>
                          <TableCell className="font-mono">{frame.timestamp_formatted}</TableCell>
                          <TableCell>
                            {frame.nsfw.detected ? (
                              <div className="flex items-center gap-1.5">
                                <Badge variant="destructive" className="bg-red-500">
                                  {(frame.nsfw.confidence * 100).toFixed(1)}%
                                </Badge>
                                <Eye className="h-3.5 w-3.5 text-red-500" />
                              </div>
                            ) : (
                              <Badge variant="outline" className="bg-green-50 text-green-600 border-green-200">Safe</Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {frame.violence.detected ? (
                              <div className="flex items-center gap-1.5">
                                <Badge variant="destructive" className="bg-orange-500">
                                  {(frame.violence.confidence * 100).toFixed(1)}%
                                </Badge>
                                <Flame className="h-3.5 w-3.5 text-orange-500" />
                              </div>
                            ) : (
                              <Badge variant="outline" className="bg-green-50 text-green-600 border-green-200">Safe</Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {frame.profanity.detected ? (
                              <div>
                                <div className="flex items-center gap-1.5">
                                  <Badge variant="destructive" className="bg-purple-500">
                                    {(frame.profanity.confidence * 100).toFixed(1)}%
                                  </Badge>
                                  <MessageSquare className="h-3.5 w-3.5 text-purple-500" />
                                </div>
                                {frame.profanity.text && (
                                  <p className="text-xs mt-1.5 text-muted-foreground bg-muted/30 p-1.5 rounded">
                                    "{frame.profanity.text}"
                                  </p>
                                )}
                              </div>
                            ) : (
                              <Badge variant="outline" className="bg-green-50 text-green-600 border-green-200">None</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="bg-muted rounded-full p-4 mb-4">
                    <AlertCircle className="h-12 w-12 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-medium">No detailed frame data available</h3>
                  <p className="text-sm text-muted-foreground max-w-md mt-2">
                    No frames with inappropriate content were detected or detailed frame analysis was not enabled.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="timeline" className="mt-6">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Content Timeline</CardTitle>
              <CardDescription>
                Visual representation of flagged content across the video timeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative h-32 w-full bg-muted/30 rounded-lg overflow-hidden border">
                {flags.map((flag, index) => {
                  // Calculate position based on timestamp
                  const maxTime = detailedResults.length > 0 
                    ? detailedResults[detailedResults.length - 1].timestamp_seconds 
                    : 60;
                  const position = (flag.timestamp / maxTime) * 100;
                  
                  return (
                    <div 
                      key={index}
                      className={`absolute w-1.5 h-full ${
                        flag.type === 'explicit' 
                          ? 'bg-red-500' 
                          : flag.type === 'violent'
                          ? 'bg-orange-500'
                          : 'bg-purple-500'
                      }`}
                      style={{ left: `${position}%` }}
                      title={`${flag.type} at ${formatTime(flag.timestamp)}`}
                    />
                  );
                })}
                
                {/* Time markers */}
                <div className="absolute bottom-0 w-full h-8 flex justify-between px-4 text-xs items-end pb-2">
                  <span className="font-mono">0:00</span>
                  <span className="font-mono">
                    {detailedResults.length > 0 
                      ? formatTime(detailedResults[detailedResults.length - 1].timestamp_seconds)
                      : '1:00'
                    }
                  </span>
                </div>
                
                {/* Add grid lines for better visualization */}
                <div className="absolute inset-0 grid grid-cols-10 pointer-events-none">
                  {Array.from({ length: 10 }).map((_, i) => (
                    <div key={i} className="border-l border-muted h-full" />
                  ))}
                </div>
              </div>
              
              <div className="mt-6 flex flex-wrap justify-center gap-6">
                <div className="flex items-center gap-2 bg-muted/30 px-3 py-2 rounded-full">
                  <div className="w-3 h-3 bg-red-500 rounded-full" />
                  <span className="text-sm">NSFW ({summary.nsfw.frames_detected})</span>
                </div>
                <div className="flex items-center gap-2 bg-muted/30 px-3 py-2 rounded-full">
                  <div className="w-3 h-3 bg-orange-500 rounded-full" />
                  <span className="text-sm">Violence ({summary.violence.frames_detected})</span>
                </div>
                <div className="flex items-center gap-2 bg-muted/30 px-3 py-2 rounded-full">
                  <div className="w-3 h-3 bg-purple-500 rounded-full" />
                  <span className="text-sm">Profanity ({summary.profanity.frames_detected})</span>
                </div>
              </div>
              
              {flags.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 mt-4 text-center">
                  <CheckCircle className="h-8 w-8 text-green-500 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No content flags detected in the timeline
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}