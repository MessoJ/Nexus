const axios = require('axios');
const ffmpeg = require('fluent-ffmpeg');
const ffmpegStatic = require('ffmpeg-static');
const winston = require('winston');
const path = require('path');
const fs = require('fs').promises;
const StorageService = require('./storageService');

// Set ffmpeg path
ffmpeg.setFfmpegPath(ffmpegStatic);

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [new winston.transports.Console()]
});

class VideoService {
  constructor() {
    this.pictoryApiKey = process.env.PICTORY_API_KEY;
    this.runwayApiKey = process.env.RUNWAY_API_KEY;
    this.storageService = new StorageService();
    this.tempDir = '/tmp/nexus-videos';
    
    // Ensure temp directory exists
    this.ensureTempDir();
  }

  async ensureTempDir() {
    try {
      await fs.mkdir(this.tempDir, { recursive: true });
    } catch (error) {
      logger.warn('Failed to create temp directory:', error.message);
    }
  }

  async generateVideo(scriptText, title, jobId) {
    try {
      if (this.pictoryApiKey) {
        return await this.generatePictoryVideo(scriptText, title, jobId);
      } else if (this.runwayApiKey) {
        return await this.generateRunwayVideo(scriptText, title, jobId);
      } else {
        return await this.generateFallbackVideo(scriptText, title, jobId);
      }
    } catch (error) {
      logger.error(`Video generation failed for job ${jobId}:`, error);
      return await this.generateFallbackVideo(scriptText, title, jobId);
    }
  }

  async generatePictoryVideo(scriptText, title, jobId) {
    logger.info(`Generating Pictory video for job: ${jobId}`);

    try {
      // Step 1: Create Pictory project
      const projectResponse = await axios.post(
        'https://api.pictory.ai/pictoryapis/v1/video/storyboard',
        {
          audio: scriptText,
          videoName: title.substring(0, 100),
          language: 'en',
          voiceover: true
        },
        {
          headers: {
            'Authorization': `Bearer ${this.pictoryApiKey}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const jobIdPictory = projectResponse.data.job_id;
      
      // Step 2: Poll for completion
      let videoUrl = null;
      let attempts = 0;
      const maxAttempts = 30; // 15 minutes max wait

      while (attempts < maxAttempts && !videoUrl) {
        await this.sleep(30000); // Wait 30 seconds
        
        const statusResponse = await axios.get(
          `https://api.pictory.ai/pictoryapis/v1/jobs/${jobIdPictory}`,
          {
            headers: {
              'Authorization': `Bearer ${this.pictoryApiKey}`
            }
          }
        );

        if (statusResponse.data.status === 'completed') {
          videoUrl = statusResponse.data.data.videoURL;
          break;
        } else if (statusResponse.data.status === 'failed') {
          throw new Error('Pictory video generation failed');
        }
        
        attempts++;
      }

      if (!videoUrl) {
        throw new Error('Pictory video generation timeout');
      }

      // Step 3: Download and upload to our storage
      const videoBuffer = await this.downloadVideo(videoUrl);
      const videoKey = `jobs/${jobId}/video_pictory.mp4`;
      const finalVideoUrl = await this.storageService.uploadBuffer(
        videoBuffer,
        videoKey,
        'video/mp4'
      );

      logger.info(`Pictory video generated successfully for job: ${jobId}`);
      return finalVideoUrl;

    } catch (error) {
      logger.error(`Pictory API error for job ${jobId}:`, error.response?.data || error.message);
      throw error;
    }
  }

  async generateRunwayVideo(scriptText, title, jobId) {
    logger.info(`Generating RunwayML video for job: ${jobId}`);

    try {
      // RunwayML Gen-2 API call
      const response = await axios.post(
        'https://api.runwayml.com/v1/generate',
        {
          model: 'gen2',
          prompt: `Create a professional video based on: ${title}. Style: clean, modern, engaging`,
          duration: Math.min(scriptText.length / 20, 10), // Max 10 seconds
          aspect_ratio: '16:9'
        },
        {
          headers: {
            'Authorization': `Bearer ${this.runwayApiKey}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const taskId = response.data.id;
      
      // Poll for completion
      let videoUrl = null;
      let attempts = 0;
      const maxAttempts = 20;

      while (attempts < maxAttempts && !videoUrl) {
        await this.sleep(15000); // Wait 15 seconds
        
        const statusResponse = await axios.get(
          `https://api.runwayml.com/v1/tasks/${taskId}`,
          {
            headers: {
              'Authorization': `Bearer ${this.runwayApiKey}`
            }
          }
        );

        if (statusResponse.data.status === 'SUCCEEDED') {
          videoUrl = statusResponse.data.output[0];
          break;
        } else if (statusResponse.data.status === 'FAILED') {
          throw new Error('RunwayML video generation failed');
        }
        
        attempts++;
      }

      if (!videoUrl) {
        throw new Error('RunwayML video generation timeout');
      }

      // Download and upload to our storage
      const videoBuffer = await this.downloadVideo(videoUrl);
      const videoKey = `jobs/${jobId}/video_runway.mp4`;
      const finalVideoUrl = await this.storageService.uploadBuffer(
        videoBuffer,
        videoKey,
        'video/mp4'
      );

      logger.info(`RunwayML video generated successfully for job: ${jobId}`);
      return finalVideoUrl;

    } catch (error) {
      logger.error(`RunwayML API error for job ${jobId}:`, error.response?.data || error.message);
      throw error;
    }
  }

  async generateFallbackVideo(scriptText, title, jobId) {
    logger.info(`Generating fallback video for job: ${jobId}`);

    try {
      const tempVideoPath = path.join(this.tempDir, `${jobId}_temp.mp4`);
      
      // Create a simple video with text overlay
      await new Promise((resolve, reject) => {
        ffmpeg()
          .input('color=c=blue:size=1920x1080:duration=10')
          .inputFormat('lavfi')
          .videoFilters([
            `drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='${title.replace(/'/g, "\\'")}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2`
          ])
          .outputOptions([
            '-c:v libx264',
            '-pix_fmt yuv420p',
            '-r 30'
          ])
          .output(tempVideoPath)
          .on('end', resolve)
          .on('error', reject)
          .run();
      });

      // Upload to storage
      const videoBuffer = await fs.readFile(tempVideoPath);
      const videoKey = `jobs/${jobId}/video_fallback.mp4`;
      const videoUrl = await this.storageService.uploadBuffer(
        videoBuffer,
        videoKey,
        'video/mp4'
      );

      // Cleanup temp file
      await fs.unlink(tempVideoPath).catch(() => {});

      logger.info(`Fallback video generated for job: ${jobId}`);
      return videoUrl;

    } catch (error) {
      logger.error(`Fallback video generation failed for job ${jobId}:`, error);
      throw error;
    }
  }

  async generateMultipleFormats(videoUrl, jobId) {
    logger.info(`Generating multiple formats for job: ${jobId}`);

    const formats = {
      'landscape': { width: 1920, height: 1080, ratio: '16:9' },
      'portrait': { width: 1080, height: 1920, ratio: '9:16' },
      'square': { width: 1080, height: 1080, ratio: '1:1' }
    };

    const results = {};

    for (const [formatName, config] of Object.entries(formats)) {
      try {
        const formattedVideoUrl = await this.resizeVideo(videoUrl, config, jobId, formatName);
        results[formatName] = {
          url: formattedVideoUrl,
          dimensions: `${config.width}x${config.height}`,
          ratio: config.ratio
        };
      } catch (error) {
        logger.warn(`Failed to generate ${formatName} format for job ${jobId}:`, error.message);
      }
    }

    return results;
  }

  async resizeVideo(videoUrl, config, jobId, formatName) {
    const tempInputPath = path.join(this.tempDir, `${jobId}_input.mp4`);
    const tempOutputPath = path.join(this.tempDir, `${jobId}_${formatName}.mp4`);

    try {
      // Download original video
      const videoBuffer = await this.downloadVideo(videoUrl);
      await fs.writeFile(tempInputPath, videoBuffer);

      // Resize video
      await new Promise((resolve, reject) => {
        ffmpeg(tempInputPath)
          .size(`${config.width}x${config.height}`)
          .aspect(config.ratio)
          .videoCodec('libx264')
          .audioCodec('aac')
          .outputOptions(['-crf 23', '-preset medium'])
          .output(tempOutputPath)
          .on('end', resolve)
          .on('error', reject)
          .run();
      });

      // Upload resized video
      const resizedBuffer = await fs.readFile(tempOutputPath);
      const videoKey = `jobs/${jobId}/video_${formatName}.mp4`;
      const resizedVideoUrl = await this.storageService.uploadBuffer(
        resizedBuffer,
        videoKey,
        'video/mp4'
      );

      // Cleanup temp files
      await fs.unlink(tempInputPath).catch(() => {});
      await fs.unlink(tempOutputPath).catch(() => {});

      return resizedVideoUrl;

    } catch (error) {
      // Cleanup on error
      await fs.unlink(tempInputPath).catch(() => {});
      await fs.unlink(tempOutputPath).catch(() => {});
      throw error;
    }
  }

  async downloadVideo(url) {
    const response = await axios.get(url, {
      responseType: 'arraybuffer',
      timeout: 300000 // 5 minutes timeout
    });
    return Buffer.from(response.data);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async addAudioToVideo(videoUrl, audioUrl, jobId) {
    const tempVideoPath = path.join(this.tempDir, `${jobId}_video.mp4`);
    const tempAudioPath = path.join(this.tempDir, `${jobId}_audio.mp3`);
    const tempOutputPath = path.join(this.tempDir, `${jobId}_final.mp4`);

    try {
      // Download video and audio
      const [videoBuffer, audioBuffer] = await Promise.all([
        this.downloadVideo(videoUrl),
        this.downloadVideo(audioUrl)
      ]);

      await fs.writeFile(tempVideoPath, videoBuffer);
      await fs.writeFile(tempAudioPath, audioBuffer);

      // Combine video and audio
      await new Promise((resolve, reject) => {
        ffmpeg()
          .input(tempVideoPath)
          .input(tempAudioPath)
          .outputOptions([
            '-c:v copy',
            '-c:a aac',
            '-map 0:v:0',
            '-map 1:a:0',
            '-shortest'
          ])
          .output(tempOutputPath)
          .on('end', resolve)
          .on('error', reject)
          .run();
      });

      // Upload final video
      const finalBuffer = await fs.readFile(tempOutputPath);
      const videoKey = `jobs/${jobId}/video_with_audio.mp4`;
      const finalVideoUrl = await this.storageService.uploadBuffer(
        finalBuffer,
        videoKey,
        'video/mp4'
      );

      // Cleanup
      await Promise.all([
        fs.unlink(tempVideoPath).catch(() => {}),
        fs.unlink(tempAudioPath).catch(() => {}),
        fs.unlink(tempOutputPath).catch(() => {})
      ]);

      return finalVideoUrl;

    } catch (error) {
      // Cleanup on error
      await Promise.all([
        fs.unlink(tempVideoPath).catch(() => {}),
        fs.unlink(tempAudioPath).catch(() => {}),
        fs.unlink(tempOutputPath).catch(() => {})
      ]);
      throw error;
    }
  }
}

module.exports = VideoService;
