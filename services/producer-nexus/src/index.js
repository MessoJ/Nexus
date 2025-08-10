const amqp = require('amqplib');
const winston = require('winston');
const { Pool } = require('pg');
require('dotenv').config();

const AudioService = require('./services/audioService');
const VideoService = require('./services/videoService');
const ImageService = require('./services/imageService');
const StorageService = require('./services/storageService');

// Configure logging
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'producer.log' })
  ]
});

// Database connection
const db = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Services initialization
const audioService = new AudioService();
const videoService = new VideoService();
const imageService = new ImageService();
const storageService = new StorageService();

class MediaProducer {
  constructor() {
    this.connection = null;
    this.channel = null;
    this.mediaQueue = process.env.MEDIA_QUEUE || 'media_queue';
  }

  async connect() {
    try {
      this.connection = await amqp.connect(process.env.RABBITMQ_URL);
      this.channel = await this.connection.createChannel();
      
      await this.channel.assertQueue(this.mediaQueue, { durable: true });
      await this.channel.prefetch(1);
      
      logger.info('Connected to RabbitMQ and ready to process media jobs');
    } catch (error) {
      logger.error('Failed to connect to RabbitMQ:', error);
      throw error;
    }
  }

  async getJob(jobId) {
    try {
      const result = await db.query(
        'SELECT id, title, script_text, analysis_json FROM content_jobs WHERE id = $1',
        [jobId]
      );
      return result.rows[0];
    } catch (error) {
      logger.error(`Failed to get job ${jobId}:`, error);
      throw error;
    }
  }

  async updateJobMedia(jobId, mediaAssets) {
    try {
      await db.query(
        `UPDATE content_jobs 
         SET media_url = $1, media_assets = $2, status = 'media_complete', updated_at = NOW() 
         WHERE id = $3`,
        [mediaAssets.audio?.url, JSON.stringify(mediaAssets), jobId]
      );
      logger.info(`Updated job ${jobId} with media assets`);
    } catch (error) {
      logger.error(`Failed to update job ${jobId}:`, error);
      throw error;
    }
  }

  async processMediaJob(jobData) {
    const { job_id: jobId } = jobData;
    logger.info(`Processing media generation for job: ${jobId}`);

    try {
      const job = await this.getJob(jobId);
      if (!job) {
        throw new Error(`Job ${jobId} not found`);
      }

      const { title, script_text, analysis_json } = job;
      const analysis = typeof analysis_json === 'string' 
        ? JSON.parse(analysis_json) 
        : analysis_json || {};

      // Generate media assets in parallel
      const mediaPromises = [];

      // 1. Audio Generation (ElevenLabs TTS)
      if (script_text) {
        mediaPromises.push(
          audioService.generateAudio(script_text, jobId)
            .then(audioUrl => ({ type: 'audio', url: audioUrl }))
        );
      }

      // 2. Thumbnail Generation (DALL-E)
      if (title) {
        mediaPromises.push(
          imageService.generateThumbnail(title, analysis.thumbnail_concepts || [], jobId)
            .then(thumbnailUrl => ({ type: 'thumbnail', url: thumbnailUrl }))
        );
      }

      // 3. Video Generation (if script is suitable)
      if (script_text && script_text.length > 100) {
        mediaPromises.push(
          videoService.generateVideo(script_text, title, jobId)
            .then(videoUrl => ({ type: 'video', url: videoUrl }))
        );
      }

      // Wait for all media generation to complete
      const mediaResults = await Promise.allSettled(mediaPromises);
      
      // Process results
      const mediaAssets = {};
      const errors = [];

      mediaResults.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          const { type, url } = result.value;
          mediaAssets[type] = { url, generated_at: new Date().toISOString() };
        } else {
          errors.push(`${['audio', 'thumbnail', 'video'][index]}: ${result.reason.message}`);
        }
      });

      // Generate multiple format versions if video was created
      if (mediaAssets.video) {
        try {
          const formats = await videoService.generateMultipleFormats(
            mediaAssets.video.url, 
            jobId
          );
          mediaAssets.video.formats = formats;
        } catch (error) {
          logger.warn(`Failed to generate multiple formats for ${jobId}:`, error.message);
        }
      }

      // Update job with media assets
      await this.updateJobMedia(jobId, mediaAssets);

      if (errors.length > 0) {
        logger.warn(`Job ${jobId} completed with some errors:`, errors);
      } else {
        logger.info(`Media generation completed successfully for job: ${jobId}`);
      }

      return mediaAssets;

    } catch (error) {
      logger.error(`Failed to process media job ${jobId}:`, error);
      
      // Update job status to failed
      try {
        await db.query(
          'UPDATE content_jobs SET status = $1, updated_at = NOW() WHERE id = $2',
          ['failed', jobId]
        );
      } catch (dbError) {
        logger.error(`Failed to update job status for ${jobId}:`, dbError);
      }
      
      throw error;
    }
  }

  async handleMessage(msg) {
    if (!msg) return;

    try {
      const jobData = JSON.parse(msg.content.toString());
      await this.processMediaJob(jobData);
      this.channel.ack(msg);
    } catch (error) {
      logger.error('Error processing message:', error);
      this.channel.nack(msg, false, false); // Don't requeue failed jobs
    }
  }

  async start() {
    await this.connect();
    
    this.channel.consume(this.mediaQueue, (msg) => {
      this.handleMessage(msg);
    });

    logger.info(`Media Producer started, listening on queue: ${this.mediaQueue}`);

    // Graceful shutdown
    process.on('SIGINT', async () => {
      logger.info('Shutting down Media Producer...');
      if (this.channel) await this.channel.close();
      if (this.connection) await this.connection.close();
      await db.end();
      process.exit(0);
    });
  }
}

// Start the service
const producer = new MediaProducer();
producer.start().catch(error => {
  logger.error('Failed to start Media Producer:', error);
  process.exit(1);
});
