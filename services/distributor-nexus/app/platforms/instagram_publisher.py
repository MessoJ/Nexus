import os
import logging
from typing import Dict, Optional
import requests
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.iguser import IGUser
from facebook_business.adobjects.igmedia import IGMedia
import time

logger = logging.getLogger(__name__)

class InstagramPublisher:
    def __init__(self):
        self.access_token = os.getenv('INSTAGRAM_ACCESS_TOKEN')
        self.instagram_account_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        
        if not all([self.access_token, self.instagram_account_id]):
            logger.warning("Instagram credentials not fully configured")
        
        if self.access_token:
            FacebookAdsApi.init(access_token=self.access_token)

    async def publish(self, content: Dict) -> Dict:
        """Publish content to Instagram"""
        try:
            if not self._has_credentials():
                raise ValueError("Instagram credentials not configured")

            media_url = content.get('media_url')
            caption = content.get('caption', content.get('title', ''))
            
            # Add hashtags to caption
            hashtags = content.get('hashtags', [])
            if hashtags:
                hashtag_text = '\n\n' + ' '.join(hashtags[:30])  # Instagram allows up to 30 hashtags
                caption += hashtag_text

            # Determine media type and format
            media_format = content.get('media_format', 'square')
            media_assets = content.get('media_assets', {})
            
            # Get the appropriate media URL based on format
            if 'video' in media_assets:
                video_formats = media_assets['video'].get('formats', {})
                if media_format == 'square' and 'square' in video_formats:
                    media_url = video_formats['square']
                elif media_format == 'portrait' and 'portrait' in video_formats:
                    media_url = video_formats['portrait']
                else:
                    media_url = media_assets['video'].get('url', media_url)
            
            # Check if it's a video or image
            is_video = self._is_video_url(media_url)
            
            if is_video:
                return await self._publish_video(media_url, caption)
            else:
                return await self._publish_image(media_url, caption)

        except Exception as e:
            logger.error(f"Instagram publishing failed: {str(e)}")
            raise

    async def _publish_image(self, image_url: str, caption: str) -> Dict:
        """Publish image to Instagram"""
        try:
            # Create media container
            container_response = requests.post(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}/media',
                params={
                    'image_url': image_url,
                    'caption': caption,
                    'access_token': self.access_token
                }
            )
            
            container_response.raise_for_status()
            container_data = container_response.json()
            container_id = container_data['id']
            
            # Publish the media
            publish_response = requests.post(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}/media_publish',
                params={
                    'creation_id': container_id,
                    'access_token': self.access_token
                }
            )
            
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            media_id = publish_data['id']
            
            # Get the published post URL
            post_url = await self._get_post_url(media_id)
            
            logger.info(f"Successfully published image to Instagram: {post_url}")
            
            return {
                'platform': 'instagram',
                'url': post_url,
                'media_id': media_id,
                'status': 'published',
                'media_type': 'image'
            }

        except Exception as e:
            logger.error(f"Instagram image publishing failed: {str(e)}")
            raise

    async def _publish_video(self, video_url: str, caption: str) -> Dict:
        """Publish video to Instagram"""
        try:
            # Create video media container
            container_response = requests.post(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}/media',
                params={
                    'video_url': video_url,
                    'caption': caption,
                    'media_type': 'VIDEO',
                    'access_token': self.access_token
                }
            )
            
            container_response.raise_for_status()
            container_data = container_response.json()
            container_id = container_data['id']
            
            # Wait for video processing
            await self._wait_for_video_processing(container_id)
            
            # Publish the video
            publish_response = requests.post(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}/media_publish',
                params={
                    'creation_id': container_id,
                    'access_token': self.access_token
                }
            )
            
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            media_id = publish_data['id']
            
            # Get the published post URL
            post_url = await self._get_post_url(media_id)
            
            logger.info(f"Successfully published video to Instagram: {post_url}")
            
            return {
                'platform': 'instagram',
                'url': post_url,
                'media_id': media_id,
                'status': 'published',
                'media_type': 'video'
            }

        except Exception as e:
            logger.error(f"Instagram video publishing failed: {str(e)}")
            raise

    async def publish_story(self, content: Dict) -> Dict:
        """Publish content to Instagram Stories"""
        try:
            if not self._has_credentials():
                raise ValueError("Instagram credentials not configured")

            media_url = content.get('media_url')
            
            # Stories don't support captions, but we can add text overlay
            # This would require more complex media manipulation
            
            # Create story media container
            container_response = requests.post(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}/media',
                params={
                    'image_url' if not self._is_video_url(media_url) else 'video_url': media_url,
                    'media_type': 'STORIES',
                    'access_token': self.access_token
                }
            )
            
            container_response.raise_for_status()
            container_data = container_response.json()
            container_id = container_data['id']
            
            # Publish the story
            publish_response = requests.post(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}/media_publish',
                params={
                    'creation_id': container_id,
                    'access_token': self.access_token
                }
            )
            
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            media_id = publish_data['id']
            
            logger.info(f"Successfully published story to Instagram: {media_id}")
            
            return {
                'platform': 'instagram',
                'media_id': media_id,
                'status': 'published',
                'media_type': 'story'
            }

        except Exception as e:
            logger.error(f"Instagram story publishing failed: {str(e)}")
            raise

    async def _wait_for_video_processing(self, container_id: str, max_wait: int = 300):
        """Wait for Instagram video processing to complete"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = requests.get(
                f'https://graph.facebook.com/v18.0/{container_id}',
                params={
                    'fields': 'status_code',
                    'access_token': self.access_token
                }
            )
            
            status_response.raise_for_status()
            status_data = status_response.json()
            
            status_code = status_data.get('status_code')
            
            if status_code == 'FINISHED':
                logger.info(f"Video processing completed for container {container_id}")
                return
            elif status_code == 'ERROR':
                raise Exception(f"Video processing failed for container {container_id}")
            
            # Wait before checking again
            time.sleep(10)
        
        raise Exception(f"Video processing timeout for container {container_id}")

    async def _get_post_url(self, media_id: str) -> str:
        """Get the public URL for an Instagram post"""
        try:
            response = requests.get(
                f'https://graph.facebook.com/v18.0/{media_id}',
                params={
                    'fields': 'permalink',
                    'access_token': self.access_token
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data.get('permalink', f'https://www.instagram.com/p/{media_id}/')
            
        except Exception as e:
            logger.warning(f"Failed to get post URL for {media_id}: {str(e)}")
            return f'https://www.instagram.com/p/{media_id}/'

    def _is_video_url(self, url: str) -> bool:
        """Check if URL points to a video file"""
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        return any(url.lower().endswith(ext) for ext in video_extensions)

    def _has_credentials(self) -> bool:
        """Check if all required credentials are available"""
        return all([self.access_token, self.instagram_account_id])

    async def get_media_analytics(self, media_id: str) -> Dict:
        """Get analytics for an Instagram post"""
        try:
            response = requests.get(
                f'https://graph.facebook.com/v18.0/{media_id}/insights',
                params={
                    'metric': 'engagement,impressions,reach,saved',
                    'access_token': self.access_token
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse metrics
            metrics = {}
            for item in data.get('data', []):
                metrics[item['name']] = item['values'][0]['value']
            
            # Get basic media info
            media_response = requests.get(
                f'https://graph.facebook.com/v18.0/{media_id}',
                params={
                    'fields': 'like_count,comments_count,timestamp,media_type',
                    'access_token': self.access_token
                }
            )
            
            media_response.raise_for_status()
            media_data = media_response.json()
            
            return {
                'platform': 'instagram',
                'media_id': media_id,
                'likes': media_data.get('like_count', 0),
                'comments': media_data.get('comments_count', 0),
                'engagement': metrics.get('engagement', 0),
                'impressions': metrics.get('impressions', 0),
                'reach': metrics.get('reach', 0),
                'saved': metrics.get('saved', 0),
                'timestamp': media_data.get('timestamp'),
                'media_type': media_data.get('media_type')
            }
            
        except Exception as e:
            logger.error(f"Failed to get Instagram analytics for {media_id}: {str(e)}")
            raise

    async def delete_media(self, media_id: str) -> bool:
        """Delete an Instagram post"""
        try:
            response = requests.delete(
                f'https://graph.facebook.com/v18.0/{media_id}',
                params={
                    'access_token': self.access_token
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully deleted Instagram media {media_id}")
                return True
            else:
                logger.warning(f"Failed to delete Instagram media {media_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting Instagram media {media_id}: {str(e)}")
            return False

    async def get_account_info(self) -> Dict:
        """Get Instagram account information"""
        try:
            response = requests.get(
                f'https://graph.facebook.com/v18.0/{self.instagram_account_id}',
                params={
                    'fields': 'account_type,username,name,profile_picture_url,followers_count,follows_count,media_count',
                    'access_token': self.access_token
                }
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get Instagram account info: {str(e)}")
            raise
