const axios = require('axios');
const { createCanvas, loadImage } = require('canvas');
const winston = require('winston');
const StorageService = require('./storageService');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [new winston.transports.Console()]
});

class ImageService {
  constructor() {
    this.openaiApiKey = process.env.OPENAI_API_KEY;
    this.midjourneyApiKey = process.env.MIDJOURNEY_API_KEY;
    this.storageService = new StorageService();
  }

  async generateThumbnail(title, concepts = [], jobId) {
    try {
      if (this.openaiApiKey) {
        return await this.generateDALLEThumbnail(title, concepts, jobId);
      } else if (this.midjourneyApiKey) {
        return await this.generateMidjourneyThumbnail(title, concepts, jobId);
      } else {
        return await this.generateFallbackThumbnail(title, jobId);
      }
    } catch (error) {
      logger.error(`Thumbnail generation failed for job ${jobId}:`, error);
      return await this.generateFallbackThumbnail(title, jobId);
    }
  }

  async generateDALLEThumbnail(title, concepts, jobId) {
    logger.info(`Generating DALL-E thumbnail for job: ${jobId}`);

    try {
      const prompt = this.createThumbnailPrompt(title, concepts);
      
      const response = await axios.post(
        'https://api.openai.com/v1/images/generations',
        {
          model: "dall-e-3",
          prompt: prompt,
          n: 1,
          size: "1792x1024", // 16:9 aspect ratio for YouTube
          quality: "hd",
          style: "vivid"
        },
        {
          headers: {
            'Authorization': `Bearer ${this.openaiApiKey}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const imageUrl = response.data.data[0].url;
      
      // Download and upload to our storage
      const imageBuffer = await this.downloadImage(imageUrl);
      const imageKey = `jobs/${jobId}/thumbnail_dalle.png`;
      const finalImageUrl = await this.storageService.uploadBuffer(
        imageBuffer,
        imageKey,
        'image/png'
      );

      logger.info(`DALL-E thumbnail generated successfully for job: ${jobId}`);
      return finalImageUrl;

    } catch (error) {
      logger.error(`DALL-E API error for job ${jobId}:`, error.response?.data || error.message);
      throw error;
    }
  }

  async generateMidjourneyThumbnail(title, concepts, jobId) {
    logger.info(`Generating Midjourney thumbnail for job: ${jobId}`);

    try {
      const prompt = this.createThumbnailPrompt(title, concepts, 'midjourney');
      
      // Note: This is a placeholder for Midjourney API integration
      // You would need to implement the actual Midjourney API calls
      const response = await axios.post(
        'https://api.midjourney.com/v1/imagine',
        {
          prompt: prompt,
          aspect_ratio: '16:9'
        },
        {
          headers: {
            'Authorization': `Bearer ${this.midjourneyApiKey}`,
            'Content-Type': 'application/json'
          }
        }
      );

      // Poll for completion (similar to video services)
      const taskId = response.data.task_id;
      let imageUrl = null;
      let attempts = 0;
      const maxAttempts = 20;

      while (attempts < maxAttempts && !imageUrl) {
        await this.sleep(10000); // Wait 10 seconds
        
        const statusResponse = await axios.get(
          `https://api.midjourney.com/v1/tasks/${taskId}`,
          {
            headers: {
              'Authorization': `Bearer ${this.midjourneyApiKey}`
            }
          }
        );

        if (statusResponse.data.status === 'completed') {
          imageUrl = statusResponse.data.image_url;
          break;
        } else if (statusResponse.data.status === 'failed') {
          throw new Error('Midjourney thumbnail generation failed');
        }
        
        attempts++;
      }

      if (!imageUrl) {
        throw new Error('Midjourney thumbnail generation timeout');
      }

      // Download and upload to our storage
      const imageBuffer = await this.downloadImage(imageUrl);
      const imageKey = `jobs/${jobId}/thumbnail_midjourney.png`;
      const finalImageUrl = await this.storageService.uploadBuffer(
        imageBuffer,
        imageKey,
        'image/png'
      );

      logger.info(`Midjourney thumbnail generated successfully for job: ${jobId}`);
      return finalImageUrl;

    } catch (error) {
      logger.error(`Midjourney API error for job ${jobId}:`, error.response?.data || error.message);
      throw error;
    }
  }

  async generateFallbackThumbnail(title, jobId) {
    logger.info(`Generating fallback thumbnail for job: ${jobId}`);

    try {
      // Create a professional-looking thumbnail using Canvas
      const canvas = createCanvas(1792, 1024); // 16:9 aspect ratio
      const ctx = canvas.getContext('2d');

      // Background gradient
      const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
      gradient.addColorStop(0, '#667eea');
      gradient.addColorStop(1, '#764ba2');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Add subtle pattern
      ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
      for (let i = 0; i < canvas.width; i += 100) {
        for (let j = 0; j < canvas.height; j += 100) {
          ctx.fillRect(i, j, 50, 50);
        }
      }

      // Title text
      const maxWidth = canvas.width - 100;
      const words = title.split(' ');
      const lines = this.wrapText(words, maxWidth, ctx, '48px Arial');

      ctx.fillStyle = 'white';
      ctx.font = 'bold 48px Arial';
      ctx.textAlign = 'center';
      ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
      ctx.shadowBlur = 4;
      ctx.shadowOffsetX = 2;
      ctx.shadowOffsetY = 2;

      const startY = (canvas.height - (lines.length * 60)) / 2;
      lines.forEach((line, index) => {
        ctx.fillText(line, canvas.width / 2, startY + (index * 60));
      });

      // Add "AI Generated" watermark
      ctx.font = '24px Arial';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
      ctx.shadowBlur = 0;
      ctx.textAlign = 'right';
      ctx.fillText('🤖 AI Generated', canvas.width - 20, canvas.height - 20);

      // Convert to buffer
      const buffer = canvas.toBuffer('image/png');
      
      // Upload to storage
      const imageKey = `jobs/${jobId}/thumbnail_fallback.png`;
      const imageUrl = await this.storageService.uploadBuffer(
        buffer,
        imageKey,
        'image/png'
      );

      logger.info(`Fallback thumbnail generated for job: ${jobId}`);
      return imageUrl;

    } catch (error) {
      logger.error(`Fallback thumbnail generation failed for job ${jobId}:`, error);
      throw error;
    }
  }

  createThumbnailPrompt(title, concepts = [], style = 'dalle') {
    let basePrompt = `Create a professional, eye-catching thumbnail for: "${title}"`;
    
    if (concepts.length > 0) {
      basePrompt += ` incorporating these concepts: ${concepts.join(', ')}`;
    }

    if (style === 'dalle') {
      basePrompt += '. Style: modern, clean, high-contrast, suitable for social media. Include bold text elements and vibrant colors.';
    } else if (style === 'midjourney') {
      basePrompt += ' --ar 16:9 --style raw --v 6';
    }

    return basePrompt;
  }

  async generateMultipleThumbnails(title, concepts, jobId, count = 3) {
    const thumbnails = {};
    
    for (let i = 0; i < count; i++) {
      try {
        const variation = i === 0 ? '' : ` variation ${i + 1}`;
        const thumbnailUrl = await this.generateThumbnail(
          title + variation, 
          concepts, 
          `${jobId}_thumb_${i}`
        );
        thumbnails[`option_${i + 1}`] = thumbnailUrl;
      } catch (error) {
        logger.warn(`Failed to generate thumbnail ${i + 1} for job ${jobId}:`, error.message);
      }
    }

    return thumbnails;
  }

  async generateSocialMediaAssets(title, jobId) {
    const assets = {};
    const formats = {
      'instagram_post': { width: 1080, height: 1080 },
      'instagram_story': { width: 1080, height: 1920 },
      'twitter_post': { width: 1200, height: 675 },
      'linkedin_post': { width: 1200, height: 627 },
      'facebook_post': { width: 1200, height: 630 }
    };

    for (const [formatName, dimensions] of Object.entries(formats)) {
      try {
        const assetUrl = await this.generateCustomAsset(title, dimensions, jobId, formatName);
        assets[formatName] = assetUrl;
      } catch (error) {
        logger.warn(`Failed to generate ${formatName} asset for job ${jobId}:`, error.message);
      }
    }

    return assets;
  }

  async generateCustomAsset(title, dimensions, jobId, formatName) {
    const canvas = createCanvas(dimensions.width, dimensions.height);
    const ctx = canvas.getContext('2d');

    // Background
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, '#667eea');
    gradient.addColorStop(1, '#764ba2');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Title
    const fontSize = Math.min(dimensions.width / 20, dimensions.height / 15);
    ctx.font = `bold ${fontSize}px Arial`;
    ctx.fillStyle = 'white';
    ctx.textAlign = 'center';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
    ctx.shadowBlur = 4;

    const maxWidth = dimensions.width - 40;
    const words = title.split(' ');
    const lines = this.wrapText(words, maxWidth, ctx, ctx.font);
    
    const startY = (dimensions.height - (lines.length * fontSize * 1.2)) / 2;
    lines.forEach((line, index) => {
      ctx.fillText(line, dimensions.width / 2, startY + (index * fontSize * 1.2));
    });

    // Convert to buffer and upload
    const buffer = canvas.toBuffer('image/png');
    const imageKey = `jobs/${jobId}/${formatName}.png`;
    return await this.storageService.uploadBuffer(buffer, imageKey, 'image/png');
  }

  wrapText(words, maxWidth, ctx, font) {
    ctx.font = font;
    const lines = [];
    let currentLine = '';

    for (const word of words) {
      const testLine = currentLine + (currentLine ? ' ' : '') + word;
      const metrics = ctx.measureText(testLine);
      
      if (metrics.width > maxWidth && currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        currentLine = testLine;
      }
    }
    
    if (currentLine) {
      lines.push(currentLine);
    }

    return lines;
  }

  async downloadImage(url) {
    const response = await axios.get(url, {
      responseType: 'arraybuffer',
      timeout: 60000
    });
    return Buffer.from(response.data);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = ImageService;
