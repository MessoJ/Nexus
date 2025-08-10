const AWS = require('aws-sdk');
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [new winston.transports.Console()]
});

class StorageService {
  constructor() {
    this.s3 = new AWS.S3({
      endpoint: process.env.S3_ENDPOINT_URL || 'http://minio:9000',
      accessKeyId: process.env.MINIO_ROOT_USER || 'minioadmin',
      secretAccessKey: process.env.MINIO_ROOT_PASSWORD || 'minioadmin',
      s3ForcePathStyle: true,
      signatureVersion: 'v4',
      region: 'us-east-1'
    });
    
    this.bucket = process.env.S3_BUCKET || 'relayforge-assets';
    this.publicBaseUrl = process.env.PUBLIC_S3_BASE_URL || 'http://localhost:9000';
    
    this.ensureBucket();
  }

  async ensureBucket() {
    try {
      await this.s3.headBucket({ Bucket: this.bucket }).promise();
      logger.info(`Bucket ${this.bucket} exists`);
    } catch (error) {
      if (error.statusCode === 404) {
        try {
          await this.s3.createBucket({ Bucket: this.bucket }).promise();
          logger.info(`Created bucket ${this.bucket}`);
        } catch (createError) {
          logger.error(`Failed to create bucket ${this.bucket}:`, createError);
        }
      } else {
        logger.error(`Error checking bucket ${this.bucket}:`, error);
      }
    }
  }

  async uploadBuffer(buffer, key, contentType) {
    try {
      const params = {
        Bucket: this.bucket,
        Key: key,
        Body: buffer,
        ContentType: contentType,
        ACL: 'public-read'
      };

      const result = await this.s3.upload(params).promise();
      const publicUrl = `${this.publicBaseUrl}/${this.bucket}/${key}`;
      
      logger.info(`Uploaded ${key} to storage`);
      return publicUrl;
      
    } catch (error) {
      logger.error(`Failed to upload ${key}:`, error);
      throw error;
    }
  }

  async uploadFile(filePath, key, contentType) {
    const fs = require('fs');
    const buffer = fs.readFileSync(filePath);
    return await this.uploadBuffer(buffer, key, contentType);
  }

  async deleteFile(key) {
    try {
      await this.s3.deleteObject({
        Bucket: this.bucket,
        Key: key
      }).promise();
      
      logger.info(`Deleted ${key} from storage`);
      return true;
      
    } catch (error) {
      logger.error(`Failed to delete ${key}:`, error);
      return false;
    }
  }

  async getSignedUrl(key, expiresIn = 3600) {
    try {
      const url = await this.s3.getSignedUrlPromise('getObject', {
        Bucket: this.bucket,
        Key: key,
        Expires: expiresIn
      });
      
      return url;
      
    } catch (error) {
      logger.error(`Failed to generate signed URL for ${key}:`, error);
      throw error;
    }
  }

  async listFiles(prefix = '') {
    try {
      const result = await this.s3.listObjectsV2({
        Bucket: this.bucket,
        Prefix: prefix
      }).promise();
      
      return result.Contents.map(obj => ({
        key: obj.Key,
        size: obj.Size,
        lastModified: obj.LastModified,
        url: `${this.publicBaseUrl}/${this.bucket}/${obj.Key}`
      }));
      
    } catch (error) {
      logger.error(`Failed to list files with prefix ${prefix}:`, error);
      throw error;
    }
  }

  async copyFile(sourceKey, destKey) {
    try {
      await this.s3.copyObject({
        Bucket: this.bucket,
        CopySource: `${this.bucket}/${sourceKey}`,
        Key: destKey
      }).promise();
      
      logger.info(`Copied ${sourceKey} to ${destKey}`);
      return `${this.publicBaseUrl}/${this.bucket}/${destKey}`;
      
    } catch (error) {
      logger.error(`Failed to copy ${sourceKey} to ${destKey}:`, error);
      throw error;
    }
  }

  getPublicUrl(key) {
    return `${this.publicBaseUrl}/${this.bucket}/${key}`;
  }
}

module.exports = StorageService;
