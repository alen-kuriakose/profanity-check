import axios from 'axios';

// Define the base URL for the API
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create an axios instance with the base URL
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Define types for the API responses
export interface VideoAnalysisResult {
  content_id: string;
  filename: string;
  flags?: {
    type: 'explicit' | 'violent' | 'profane';
    confidence: number;
    timestamp: number;
    timestamp_formatted?: string;
    frame_number?: number;
    text?: string;
  }[];
  status: string;
  content_rating: 'safe' | 'questionable' | 'explicit' | 'violent' | 'profane';
  summary?: {
    content_id: string;
    filename: string;
    total_frames_analyzed: number;
    frames_with_inappropriate_content: number;
    inappropriate_percentage: number;
    nsfw: {
      frames_detected: number;
      percentage: number;
      max_confidence: number;
    };
    violence: {
      frames_detected: number;
      percentage: number;
      max_confidence: number;
    };
    profanity: {
      frames_detected: number;
      percentage: number;
      max_confidence: number;
    };
    processing_time_seconds: number;
    frames_per_second: number;
  };
  detailed_results?: {
    frame_number: number;
    timestamp_seconds: number;
    timestamp_formatted: string;
    has_inappropriate_content: boolean;
    nsfw: {
      detected: boolean;
      confidence: number;
    };
    violence: {
      detected: boolean;
      confidence: number;
    };
    profanity: {
      detected: boolean;
      confidence: number;
      text?: string;
    };
  }[];
  model_info?: string;
}

// Interface for video list items
export interface VideoListItem {
  contentId: string;
  filename: string;
  uploadDate: string;
  status: string;
  contentRating?: 'safe' | 'questionable' | 'explicit' | 'violent' | 'profane';
  flaggedFrames?: number;
  totalFrames?: number;
  thumbnailUrl?: string;
}

// API functions for synchronous video analysis
export const videoAnalysisApi = {
  // Health check endpoint
  checkHealth: async () => {
    try {
      const response = await api.get('/video-analysis/health');
      return response.data;
    } catch (error) {
      console.error('Health check failed:', error);
      throw error;
    }
  },

  // Comprehensive video analysis (synchronous)
  analyzeVideo: async (
    file: File,
    contentId: string,
    options: {
      frameInterval?: number;
      checkNsfw?: boolean;
      checkViolence?: boolean;
      checkProfanity?: boolean;
      confidenceThreshold?: number;
    } = {}
  ): Promise<VideoAnalysisResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('content_id', contentId);
    
    // Add optional parameters
    if (options.frameInterval) {
      formData.append('frame_interval', options.frameInterval.toString());
    }
    
    if (options.checkNsfw !== undefined) {
      formData.append('check_nsfw', options.checkNsfw.toString());
    }
    
    if (options.checkViolence !== undefined) {
      formData.append('check_violence', options.checkViolence.toString());
    }
    
    if (options.checkProfanity !== undefined) {
      formData.append('check_profanity', options.checkProfanity.toString());
    }
    
    if (options.confidenceThreshold) {
      formData.append('confidence_threshold', options.confidenceThreshold.toString());
    }

    try {
      const response = await api.post('/video-analysis/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Video analysis failed:', error);
      throw error;
    }
  },

  // NSFW check only
  checkNsfw: async (
    file: File,
    options: {
      frameInterval?: number;
      confidenceThreshold?: number;
      resizeMaxDimension?: number;
    } = {}
  ) => {
    const formData = new FormData();
    formData.append('video', file);
    
    if (options.frameInterval) {
      formData.append('frame_interval', options.frameInterval.toString());
    }
    
    if (options.confidenceThreshold) {
      formData.append('confidence_threshold', options.confidenceThreshold.toString());
    }
    
    if (options.resizeMaxDimension) {
      formData.append('resize_max_dimension', options.resizeMaxDimension.toString());
    }

    try {
      const response = await api.post('/video-analysis/nsfw-check', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('NSFW check failed:', error);
      throw error;
    }
  },

  // Violence check only
  checkViolence: async (
    file: File,
    options: {
      frameInterval?: number;
      confidenceThreshold?: number;
      resizeMaxDimension?: number;
    } = {}
  ) => {
    const formData = new FormData();
    formData.append('video', file);
    
    if (options.frameInterval) {
      formData.append('frame_interval', options.frameInterval.toString());
    }
    
    if (options.confidenceThreshold) {
      formData.append('confidence_threshold', options.confidenceThreshold.toString());
    }
    
    if (options.resizeMaxDimension) {
      formData.append('resize_max_dimension', options.resizeMaxDimension.toString());
    }

    try {
      const response = await api.post('/video-analysis/violence-check', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Violence check failed:', error);
      throw error;
    }
  },

  // Profanity check only
  checkProfanity: async (
    file: File,
    options: {
      contentId?: string;
      frameInterval?: number;
      checkAudio?: boolean;
      checkFrames?: boolean;
    } = {}
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    
    // Add content_id if provided (for database storage)
    if (options.contentId) {
      formData.append('content_id', options.contentId);
    }
    
    if (options.frameInterval) {
      formData.append('frame_interval', options.frameInterval.toString());
    }
    
    if (options.checkAudio !== undefined) {
      formData.append('check_audio', options.checkAudio.toString());
    }
    
    if (options.checkFrames !== undefined) {
      formData.append('check_frames', options.checkFrames.toString());
    }

    try {
      const response = await api.post('/video-analysis/profanity-check', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      // If the response includes timestamp_results, format it to match the expected structure
      if (response.data.timestamp_results && response.data.timestamp_results.length > 0) {
        // Add detailed_results if not present
        if (!response.data.detailed_results) {
          response.data.detailed_results = response.data.timestamp_results.map((result: any) => ({
            frame_number: result.frame_number || 0,
            timestamp_seconds: result.timestamp || 0,
            timestamp_formatted: result.timestamp_formatted || '0:00',
            has_inappropriate_content: result.has_profanity || false,
            nsfw: { detected: false, confidence: 0 },
            violence: { detected: false, confidence: 0 },
            profanity: {
              detected: result.has_profanity || false,
              confidence: result.confidence || 0,
              text: result.text || ''
            }
          }));
        }
        
        // Add flags if not present
        if (!response.data.flags && response.data.has_profanity) {
          response.data.flags = [{
            type: 'profane',
            confidence: response.data.confidence || 0,
            timestamp: 0,
            timestamp_formatted: '0:00',
            frame_number: 0,
            text: response.data.transcript || ''
          }];
        }
      }
      
      return response.data;
    } catch (error) {
      console.error('Profanity check failed:', error);
      throw error;
    }
  },
};

// API functions for asynchronous video analysis
export const asyncVideoAnalysisApi = {
  // Health check endpoint
  checkHealth: async () => {
    try {
      const response = await api.get('/video-analysis-async/health');
      return response.data;
    } catch (error) {
      console.error('Async health check failed:', error);
      throw error;
    }
  },

  // Upload a video for asynchronous analysis
  uploadVideo: async (
    file: File,
    contentId: string,
    analyze: boolean = true
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('content_id', contentId);
    formData.append('analyze', analyze.toString());

    try {
      const response = await api.post('/video-analysis-async/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('Video upload failed:', error);
      throw error;
    }
  },

  // Check the status of an asynchronous analysis
  checkStatus: async (contentId: string) => {
    try {
      const response = await api.get(`/video-analysis-async/status/${contentId}`);
      return response.data;
    } catch (error) {
      console.error('Status check failed:', error);
      throw error;
    }
  },

  // Get the results of an asynchronous analysis
  getResults: async (contentId: string, includeDetails: boolean = true) => {
    try {
      const response = await api.get(
        `/video-analysis-async/results/${contentId}?include_details=true`
      );
      
      // Ensure all required properties exist with default values
      const data = response.data;
      
      // Add default values for missing properties
      if (!data.flags) data.flags = [];
      if (!data.summary) {
        data.summary = {
          content_id: data.content_id || contentId,
          filename: data.filename || '',
          total_frames_analyzed: 0,
          frames_with_inappropriate_content: 0,
          inappropriate_percentage: 0,
          nsfw: { frames_detected: 0, percentage: 0, max_confidence: 0 },
          violence: { frames_detected: 0, percentage: 0, max_confidence: 0 },
          profanity: { frames_detected: 0, percentage: 0, max_confidence: 0 },
          processing_time_seconds: 0,
          frames_per_second: 0
        };
      } else {
        // Ensure nested objects exist
        if (!data.summary.nsfw) data.summary.nsfw = { frames_detected: 0, percentage: 0, max_confidence: 0 };
        if (!data.summary.violence) data.summary.violence = { frames_detected: 0, percentage: 0, max_confidence: 0 };
        if (!data.summary.profanity) data.summary.profanity = { frames_detected: 0, percentage: 0, max_confidence: 0 };
      }
      
      // Ensure detailed_results exists
      if (!data.detailed_results) data.detailed_results = [];
      
      return data;
    } catch (error) {
      console.error('Failed to get results:', error);
      throw error;
    }
  },

  // Trigger analysis for a previously uploaded video
  triggerAnalysis: async (contentId: string) => {
    try {
      const response = await api.post(`/video-analysis-async/analyze/${contentId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to trigger analysis:', error);
      throw error;
    }
  },

  // Get all analyzed videos from the API
  getAllVideos: async (limit: number = 100, offset: number = 0): Promise<VideoListItem[]> => {
    try {
      // Get videos from API
      const response = await api.get(`/video-analysis-async/videos?limit=${limit}&offset=${offset}`);
      
      // Map API response to VideoListItem format
      return response.data.map((video: any) => ({
        contentId: video.content_id,
        filename: video.filename,
        uploadDate: video.upload_date,
        status: video.status,
        contentRating: video.content_rating,
        flaggedFrames: video.flagged_frames,
        totalFrames: video.total_frames
      }));
    } catch (error) {
      console.error('Failed to get videos from API:', error);
      
      // Fallback to localStorage if API fails
      try {
        const storedVideos = localStorage.getItem('analyzedVideos');
        if (storedVideos) {
          return JSON.parse(storedVideos);
        }
      } catch (e) {
        console.error('Failed to get videos from storage:', e);
      }
      
      return [];
    }
  },

  // Add a video to the list in localStorage (for backup/offline support)
  addVideoToList: async (video: VideoListItem): Promise<boolean> => {
    try {
      // Store in localStorage as backup
      const storedVideos = localStorage.getItem('analyzedVideos');
      let videos: VideoListItem[] = [];
      
      if (storedVideos) {
        videos = JSON.parse(storedVideos);
      }
      
      // Check if video already exists
      const existingIndex = videos.findIndex(v => v.contentId === video.contentId);
      
      if (existingIndex >= 0) {
        // Update existing video
        videos[existingIndex] = { ...videos[existingIndex], ...video };
      } else {
        // Add new video
        videos.push(video);
      }
      
      // Save back to localStorage
      localStorage.setItem('analyzedVideos', JSON.stringify(videos));
      return true;
    } catch (error) {
      console.error('Failed to add video to list:', error);
      return false;
    }
  }
};

export default api;