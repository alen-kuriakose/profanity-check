'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toaster } from '@/components/ui/sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { VideoListItem, asyncVideoAnalysisApi } from '@/lib/api';
import { Shield, Search, FileVideo, Clock, CheckCircle, AlertTriangle, Loader2, Plus, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

export default function VideosPage() {
  const router = useRouter();
  const [videos, setVideos] = useState<VideoListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const limit = 20; // Number of videos per page

  useEffect(() => {
    fetchVideos();
  }, [page]);

  const fetchVideos = async () => {
    try {
      setLoading(true);
      const videoList = await asyncVideoAnalysisApi.getAllVideos(limit, page * limit);
      
      if (videoList.length < limit) {
        setHasMore(false);
      }
      
      if (page === 0) {
        setVideos(videoList);
      } else {
        setVideos(prev => [...prev, ...videoList]);
      }
    } catch (error) {
      console.error('Failed to fetch videos:', error);
      toast.error('Failed to load video list');
    } finally {
      setLoading(false);
    }
  };
  
  const handleLoadMore = () => {
    if (!loading && hasMore) {
      setPage(prev => prev + 1);
    }
  };

  const refreshVideoStatus = async (contentId: string) => {
    try {
      setRefreshing(true);
      const statusResponse = await asyncVideoAnalysisApi.checkStatus(contentId);
      
      if (statusResponse.video_status === 'completed') {
        const results = await asyncVideoAnalysisApi.getResults(contentId, false);
        
        // Ensure summary exists with default values
        const summary = results.summary || {
          frames_with_inappropriate_content: 0,
          total_frames_analyzed: 0
        };
        
        // Update video in list
        await asyncVideoAnalysisApi.addVideoToList({
          contentId: results.content_id,
          filename: results.filename,
          uploadDate: new Date().toISOString(),
          status: 'completed',
          contentRating: results.content_rating || 'safe',
          flaggedFrames: summary.frames_with_inappropriate_content || 0,
          totalFrames: summary.total_frames_analyzed || 0
        });
        
        // Refresh the list
        fetchVideos();
        toast.success('Video status updated');
      } else {
        toast.info(`Video status: ${statusResponse.video_status}`);
      }
    } catch (error) {
      console.error('Failed to refresh video status:', error);
      toast.error('Failed to update video status');
    } finally {
      setRefreshing(false);
    }
  };

  const handleViewResults = (contentId: string) => {
    router.push(`/results?contentId=${contentId}`);
  };

  const handleUploadNew = () => {
    router.push('/');
  };

  // Filter videos based on search term
  const filteredVideos = videos.filter(video => 
    video.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    video.contentId.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Helper function to get color based on content rating
  const getRatingColor = (rating?: string) => {
    if (!rating) return 'bg-gray-500';
    
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

  // Helper function to format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <main className="min-h-screen ">
      <Toaster />
      
      <header className="border-b">
        <div className="container mx-auto py-4 px-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold">Video Analysis</h1>
          </div>
          <Button onClick={handleUploadNew} className="gap-1">
            <Plus className="h-4 w-4" />
            Upload New Video
          </Button>
        </div>
      </header>
      
      <div className="container mx-auto py-8 px-4">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h2 className="text-2xl font-bold">Analyzed Videos</h2>
              <p className="text-muted-foreground mt-1">
                View and manage your analyzed videos
              </p>
            </div>
            
            <div className="flex items-center gap-2">
              <div className="relative w-full md:w-64">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search videos..."
                  className="pl-9"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <Button 
                variant="outline" 
                size="icon" 
                onClick={() => {
                  setPage(0);
                  setHasMore(true);
                  fetchVideos();
                }}
                disabled={loading}
                title="Refresh video list"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
          
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <Loader2 className="h-12 w-12 text-primary animate-spin mb-4" />
              <h2 className="text-xl font-semibold">Loading Videos</h2>
              <p className="text-muted-foreground mt-2">Please wait while we fetch your videos...</p>
            </div>
          ) : videos.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="bg-muted/30 rounded-full p-6 mb-4">
                <FileVideo className="h-12 w-12 text-muted-foreground" />
              </div>
              <h2 className="text-xl font-semibold">No Videos Found</h2>
              <p className="text-muted-foreground mt-2 max-w-md">
                You haven't analyzed any videos yet. Upload a video to get started.
              </p>
              <Button onClick={handleUploadNew} className="mt-6 gap-1">
                <Plus className="h-4 w-4" />
                Upload Video
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredVideos.map((video) => (
                <Card key={video.contentId} className="overflow-hidden hover:shadow-md transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle className="line-clamp-1">{video.filename}</CardTitle>
                        <CardDescription className="line-clamp-1">ID: {video.contentId}</CardDescription>
                      </div>
                      {video.contentRating && (
                        <Badge 
                          className={`${getRatingColor(video.contentRating)} text-white`}
                        >
                          {video.contentRating.toUpperCase()}
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Upload Date:</span>
                        <span className="font-medium">{formatDate(video.uploadDate)}</span>
                      </div>
                      
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Status:</span>
                        <div className="flex items-center gap-1.5">
                          {video.status === 'completed' ? (
                            <>
                              <CheckCircle className="h-4 w-4 text-green-500" />
                              <span className="font-medium text-green-700">Completed</span>
                            </>
                          ) : video.status === 'processing' ? (
                            <>
                              <Clock className="h-4 w-4 text-blue-500" />
                              <span className="font-medium text-blue-700">Processing</span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="h-4 w-4 text-yellow-500" />
                              <span className="font-medium text-yellow-700">{video.status}</span>
                            </>
                          )}
                        </div>
                      </div>
                      
                      {video.status === 'completed' && (
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Flagged Frames:</span>
                          <span className="font-medium">
                            {video.flaggedFrames} / {video.totalFrames}
                            {video.totalFrames && video.flaggedFrames !== undefined && (
                              <span className="text-xs ml-1 text-muted-foreground">
                                ({((video.flaggedFrames / video.totalFrames) * 100).toFixed(1)}%)
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                      
                      <div className="flex gap-2 pt-2">
                        {video.status === 'completed' ? (
                          <Button 
                            className="w-full" 
                            onClick={() => handleViewResults(video.contentId)}
                          >
                            View Results
                          </Button>
                        ) : (
                          <Button 
                            variant="outline" 
                            className="w-full gap-1" 
                            onClick={() => refreshVideoStatus(video.contentId)}
                            disabled={refreshing}
                          >
                            {refreshing ? (
                              <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Checking...
                              </>
                            ) : (
                              <>
                                <RefreshCw className="h-4 w-4" />
                                Check Status
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {hasMore && videos.length > 0 && (
                <div className="flex justify-center mt-8">
                  <Button 
                    variant="outline" 
                    onClick={handleLoadMore} 
                    disabled={loading}
                    className="gap-2"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading...
                      </>
                    ) : (
                      <>
                        Load More Videos
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      <footer className="border-t mt-auto">
        <div className="container mx-auto py-4 px-4 text-center text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} Video Analysis Platform
        </div>
      </footer>
    </main>
  );
}