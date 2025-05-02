'use client';

import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { AnalysisResults } from '@/components/analysis-results-light';
import { Toaster } from '@/components/ui/sonner';
import { Button } from '@/components/ui/button';
import { VideoAnalysisResult, asyncVideoAnalysisApi } from '@/lib/api';
import { ArrowLeft, Shield, Loader2, FileVideo } from 'lucide-react';
import { toast } from 'sonner';

export default function ResultsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const contentId = searchParams.get('contentId');
  const [analysisResults, setAnalysisResults] = useState<VideoAnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!contentId) {
      setError('No content ID provided');
      setLoading(false);
      return;
    }

    const fetchResults = async () => {
      try {
        // Always request detailed results
        const results = await asyncVideoAnalysisApi.getResults(contentId, true);
        console.log('Fetched results:', results); // Add logging to debug
        
        // Ensure detailed_results exists and has at least one item
        if (!results.detailed_results || results.detailed_results.length === 0) {
          console.warn('No detailed results found in API response');
          
          // Add a placeholder if no detailed results
          results.detailed_results = [{
            frame_number: 0,
            timestamp_seconds: 0,
            timestamp_formatted: "0:00",
            has_inappropriate_content: false,
            nsfw: { detected: false, confidence: 0 },
            violence: { detected: false, confidence: 0 },
            profanity: { detected: false, confidence: 0, text: "" }
          }];
        }
        
        setAnalysisResults(results);
      } catch (err) {
        console.error('Failed to fetch results:', err);
        setError('Failed to load analysis results. The analysis may still be in progress or the content ID is invalid.');
        toast.error('Failed to load analysis results');
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [contentId]);

  const handleBackToHome = () => {
    router.push('/');
  };

  return (
    <main className="min-h-screen white gray-800white">
      <Toaster />
      
      <header className="border-b border-gray-200 sticky top-0 z-10 backdrop-blur-md ">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-blue-600" />
            <h1 className="text-xl font-bold text-blue-600">
              Video Analysis
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Button 
              variant="secondary" 
              onClick={() => router.push('/videos')} 
              className="gap-2 hover:text-zinc-300"
            >
              <FileVideo className="h-4 w-4" />
              My Videos
            </Button>
            <Button 
              variant="ghost" 
              onClick={handleBackToHome}  
              className="gap-2 hover:text-zinc-300"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Upload
            </Button>
          </div>
        </div>
      </header>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="relative w-16 h-16">
              <Loader2 className="h-16 w-16 text-blue-500 animate-spin" />
            </div>
            <h2 className="text-2xl font-semibold mt-6 text-gray-800">Loading Analysis Results</h2>
            <p className="text-gray-500 mt-2">Please wait while we fetch the results...</p>
          </div>
        ) : error ? (
          <div className="max-w-3xl mx-auto text-center py-12">
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-red-600 mb-3">Error Loading Results</h2>
              <p className="text-gray-700 mb-6">{error}</p>
              <Button 
                onClick={handleBackToHome}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Return to Home
              </Button>
            </div>
          </div>
        ) : analysisResults ? (
          <div className="space-y-8">
            <div className="w-full">
              <h2 className="text-2xl font-bold mb-6 text-center text-blue-600">
                Content Analysis Report
              </h2>
              <AnalysisResults results={analysisResults} />
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto text-center py-12">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-yellow-600 mb-3">No Results Found</h2>
              <p className="text-gray-700 mb-6">We couldn't find any analysis results for the provided content ID.</p>
              <Button 
                onClick={handleBackToHome}
                className="bg-yellow-600 hover:bg-yellow-700 text-white"
              >
                Return to Home
              </Button>
            </div>
          </div>
        )}
      </div>
      
      <footer className="border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 text-center text-sm text-gray-500">
          &copy; {new Date().getFullYear()} Video Analysis Platform
        </div>
      </footer>
    </main>
  );
}