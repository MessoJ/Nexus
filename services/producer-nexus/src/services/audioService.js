const axios = require('axios');
const fs = require('fs');
const path = require('path');
const winston = require('winston');
const StorageService = require('./storageService');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [new winston.transports.Console()]
});

class AudioService {
  constructor() {
    this.elevenLabsApiKey = process.env.ELEVENLABS_API_KEY;
    this.elevenLabsVoiceId = process.env.ELEVENLABS_VOICE_ID || 'pNInz6obpgDQGcFmaJgB'; // Default voice
    this.storageService = new StorageService();
    
    if (!this.elevenLabsApiKey) {
      logger.warn('ElevenLabs API key not found, using fallback audio generation');
    }
  }

  async generateAudio(scriptText, jobId) {
    try {
      if (this.elevenLabsApiKey) {
        return await this.generateElevenLabsAudio(scriptText, jobId);
      } else {
        return await this.generateFallbackAudio(scriptText, jobId);
      }
    } catch (error) {
      logger.error(`Audio generation failed for job ${jobId}:`, error);
      // Fallback to dummy audio if ElevenLabs fails
      return await this.generateFallbackAudio(scriptText, jobId);
    }
  }

  async generateElevenLabsAudio(scriptText, jobId) {
    logger.info(`Generating ElevenLabs audio for job: ${jobId}`);

    const url = `https://api.elevenlabs.io/v1/text-to-speech/${this.elevenLabsVoiceId}`;
    
    const requestData = {
      text: scriptText,
      model_id: "eleven_monolingual_v1",
      voice_settings: {
        stability: 0.5,
        similarity_boost: 0.5,
        style: 0.0,
        use_speaker_boost: true
      }
    };

    try {
      const response = await axios.post(url, requestData, {
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': this.elevenLabsApiKey
        },
        responseType: 'arraybuffer'
      });

      // Save audio to storage
      const audioKey = `jobs/${jobId}/audio_elevenlabs.mp3`;
      const audioUrl = await this.storageService.uploadBuffer(
        Buffer.from(response.data),
        audioKey,
        'audio/mpeg'
      );

      logger.info(`ElevenLabs audio generated successfully for job: ${jobId}`);
      return audioUrl;

    } catch (error) {
      logger.error(`ElevenLabs API error for job ${jobId}:`, error.response?.data || error.message);
      throw error;
    }
  }

  async generateFallbackAudio(scriptText, jobId) {
    logger.info(`Generating fallback audio for job: ${jobId}`);

    // Generate a simple WAV file with silence (placeholder)
    const audioBuffer = this.createSilentAudio(Math.min(scriptText.length / 10, 30)); // Max 30 seconds
    
    const audioKey = `jobs/${jobId}/audio_fallback.wav`;
    const audioUrl = await this.storageService.uploadBuffer(
      audioBuffer,
      audioKey,
      'audio/wav'
    );

    logger.info(`Fallback audio generated for job: ${jobId}`);
    return audioUrl;
  }

  createSilentAudio(durationSeconds = 10) {
    // Create a minimal WAV file with silence
    const sampleRate = 16000;
    const numSamples = sampleRate * durationSeconds;
    const numChannels = 1;
    const bitsPerSample = 16;
    const bytesPerSample = bitsPerSample / 8;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = numSamples * blockAlign;
    const fileSize = 44 + dataSize;

    const buffer = Buffer.alloc(fileSize);
    let offset = 0;

    // WAV header
    buffer.write('RIFF', offset); offset += 4;
    buffer.writeUInt32LE(fileSize - 8, offset); offset += 4;
    buffer.write('WAVE', offset); offset += 4;
    buffer.write('fmt ', offset); offset += 4;
    buffer.writeUInt32LE(16, offset); offset += 4; // PCM format chunk size
    buffer.writeUInt16LE(1, offset); offset += 2;  // PCM format
    buffer.writeUInt16LE(numChannels, offset); offset += 2;
    buffer.writeUInt32LE(sampleRate, offset); offset += 4;
    buffer.writeUInt32LE(byteRate, offset); offset += 4;
    buffer.writeUInt16LE(blockAlign, offset); offset += 2;
    buffer.writeUInt16LE(bitsPerSample, offset); offset += 2;
    buffer.write('data', offset); offset += 4;
    buffer.writeUInt32LE(dataSize, offset); offset += 4;

    // Silent audio data (all zeros)
    buffer.fill(0, offset);

    return buffer;
  }

  async generateMultipleVoices(scriptText, jobId, voiceIds = []) {
    if (!this.elevenLabsApiKey || voiceIds.length === 0) {
      return await this.generateAudio(scriptText, jobId);
    }

    const audioVariants = {};
    
    for (const voiceId of voiceIds) {
      try {
        const originalVoiceId = this.elevenLabsVoiceId;
        this.elevenLabsVoiceId = voiceId;
        
        const audioUrl = await this.generateElevenLabsAudio(scriptText, `${jobId}_${voiceId}`);
        audioVariants[voiceId] = audioUrl;
        
        this.elevenLabsVoiceId = originalVoiceId;
      } catch (error) {
        logger.warn(`Failed to generate audio with voice ${voiceId}:`, error.message);
      }
    }

    return Object.keys(audioVariants).length > 0 ? audioVariants : await this.generateAudio(scriptText, jobId);
  }

  async getAvailableVoices() {
    if (!this.elevenLabsApiKey) {
      return [];
    }

    try {
      const response = await axios.get('https://api.elevenlabs.io/v1/voices', {
        headers: {
          'xi-api-key': this.elevenLabsApiKey
        }
      });

      return response.data.voices.map(voice => ({
        id: voice.voice_id,
        name: voice.name,
        category: voice.category
      }));
    } catch (error) {
      logger.error('Failed to fetch ElevenLabs voices:', error.message);
      return [];
    }
  }
}

module.exports = AudioService;
