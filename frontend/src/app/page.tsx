'use client';

import { useRouter } from 'next/navigation';
import { VideoUpload } from '@/components/video-upload';
import { Toaster } from '@/components/ui/sonner';
import { Button } from '@/components/ui/button';
import { Shield, FileVideo } from 'lucide-react';
import { VideoAnalysisResult } from '@/lib/api';

export default function Home() {
  const router = useRouter();

  const handleAnalysisComplete = (results: VideoAnalysisResult) => {
    // Navigate to the results page with the content ID
    router.push(`/results?contentId=${results.content_id}`);
  };

  return (
    <main className="h-screen bg-background">
      <Toaster />
      
      <header className="border-b ">
        <div className="container mx-auto py-4 px-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold">Video Analysis</h1>
          </div>
          <Button variant="outline" onClick={() => router.push('/videos')} className="gap-1">
            <FileVideo className="h-4 w-4" />
            My Videos
          </Button>
        </div>
      </header>
      
      <div className="container mx-auto py-8 px-4 h-[90%]">
        <div className=" mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold mb-2">Video Content Analysis</h2>
            <p className="text-muted-foreground">
              Upload a video to analyze it for inappropriate content including NSFW, violence, and profanity.
            </p>
          </div>
          
          <VideoUpload onAnalysisComplete={handleAnalysisComplete} />
        </div>
      </div>
      
      <footer className="border-t mt-auto bg-">
        <div className="container mx-auto py-4 px-4 text-center text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} Video Analysis Platform
        </div>
      </footer>
    </main>
  );
}
