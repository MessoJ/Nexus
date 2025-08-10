import os
import logging
from typing import Dict, Optional
import requests
from linkedin_api import Linkedin
import json

logger = logging.getLogger(__name__)

class LinkedInPublisher:
    def __init__(self):
        self.access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')
        self.client_id = os.getenv('LINKEDIN_CLIENT_ID')
        self.client_secret = os.getenv('LINKEDIN_CLIENT_SECRET')
        self.person_id = os.getenv('LINKEDIN_PERSON_ID')  # LinkedIn person URN
        
        # For company pages
        self.company_id = os.getenv('LINKEDIN_COMPANY_ID')
        
        if not self.access_token:
            logger.warning("LinkedIn credentials not configured")

    async def publish(self, content: Dict) -> Dict:
        """Publish content to LinkedIn"""
        try:
            if not self._has_credentials():
                raise ValueError("LinkedIn credentials not configured")

            text_content = content.get('text', content.get('title', ''))
            media_url = content.get('media_url')
            article_url = content.get('article_url')
            
            # Determine the type of post
            if media_url and self._is_video_url(media_url):
                return await self._publish_video_post(text_content, media_url)
            elif media_url and self._is_image_url(media_url):
                return await self._publish_image_post(text_content, media_url)
            elif article_url:
                return await self._publish_article_share(text_content, article_url)
            else:
                return await self._publish_text_post(text_content)

        except Exception as e:
            logger.error(f"LinkedIn publishing failed: {str(e)}")
            raise

    async def _publish_text_post(self, text: str) -> Dict:
        """Publish a text-only post to LinkedIn"""
        try:
            author_urn = f"urn:li:person:{self.person_id}" if self.person_id else None
            if not author_urn:
                raise ValueError("LinkedIn person ID not configured")

            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            response = requests.post(
                'https://api.linkedin.com/v2/ugcPosts',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json',
                    'X-Restli-Protocol-Version': '2.0.0'
                },
                json=post_data
            )

            response.raise_for_status()
            result = response.json()
            post_id = result['id']
            
            # Extract post URN for URL construction
            post_urn = post_id.replace('urn:li:ugcPost:', '')
            post_url = f"https://www.linkedin.com/feed/update/{post_urn}/"

            logger.info(f"Successfully published text post to LinkedIn: {post_url}")

            return {
                'platform': 'linkedin',
                'url': post_url,
                'post_id': post_id,
                'status': 'published',
                'media_type': 'text'
            }

        except Exception as e:
            logger.error(f"LinkedIn text post failed: {str(e)}")
            raise

    async def _publish_image_post(self, text: str, image_url: str) -> Dict:
        """Publish an image post to LinkedIn"""
        try:
            author_urn = f"urn:li:person:{self.person_id}"
            
            # First, upload the image
            image_urn = await self._upload_image(image_url)
            
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": "Generated content image"
                                },
                                "media": image_urn,
                                "title": {
                                    "text": "AI Generated Content"
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            response = requests.post(
                'https://api.linkedin.com/v2/ugcPosts',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json',
                    'X-Restli-Protocol-Version': '2.0.0'
                },
                json=post_data
            )

            response.raise_for_status()
            result = response.json()
            post_id = result['id']
            
            post_urn = post_id.replace('urn:li:ugcPost:', '')
            post_url = f"https://www.linkedin.com/feed/update/{post_urn}/"

            logger.info(f"Successfully published image post to LinkedIn: {post_url}")

            return {
                'platform': 'linkedin',
                'url': post_url,
                'post_id': post_id,
                'status': 'published',
                'media_type': 'image'
            }

        except Exception as e:
            logger.error(f"LinkedIn image post failed: {str(e)}")
            raise

    async def _publish_video_post(self, text: str, video_url: str) -> Dict:
        """Publish a video post to LinkedIn"""
        try:
            author_urn = f"urn:li:person:{self.person_id}"
            
            # Upload the video
            video_urn = await self._upload_video(video_url)
            
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "VIDEO",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": "Generated content video"
                                },
                                "media": video_urn,
                                "title": {
                                    "text": "AI Generated Content"
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            response = requests.post(
                'https://api.linkedin.com/v2/ugcPosts',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json',
                    'X-Restli-Protocol-Version': '2.0.0'
                },
                json=post_data
            )

            response.raise_for_status()
            result = response.json()
            post_id = result['id']
            
            post_urn = post_id.replace('urn:li:ugcPost:', '')
            post_url = f"https://www.linkedin.com/feed/update/{post_urn}/"

            logger.info(f"Successfully published video post to LinkedIn: {post_url}")

            return {
                'platform': 'linkedin',
                'url': post_url,
                'post_id': post_id,
                'status': 'published',
                'media_type': 'video'
            }

        except Exception as e:
            logger.error(f"LinkedIn video post failed: {str(e)}")
            raise

    async def _publish_article_share(self, text: str, article_url: str) -> Dict:
        """Publish an article share to LinkedIn"""
        try:
            author_urn = f"urn:li:person:{self.person_id}"
            
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "ARTICLE",
                        "media": [
                            {
                                "status": "READY",
                                "originalUrl": article_url
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            response = requests.post(
                'https://api.linkedin.com/v2/ugcPosts',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json',
                    'X-Restli-Protocol-Version': '2.0.0'
                },
                json=post_data
            )

            response.raise_for_status()
            result = response.json()
            post_id = result['id']
            
            post_urn = post_id.replace('urn:li:ugcPost:', '')
            post_url = f"https://www.linkedin.com/feed/update/{post_urn}/"

            logger.info(f"Successfully published article share to LinkedIn: {post_url}")

            return {
                'platform': 'linkedin',
                'url': post_url,
                'post_id': post_id,
                'status': 'published',
                'media_type': 'article'
            }

        except Exception as e:
            logger.error(f"LinkedIn article share failed: {str(e)}")
            raise

    async def _upload_image(self, image_url: str) -> str:
        """Upload image to LinkedIn and return asset URN"""
        try:
            # Download image
            image_response = requests.get(image_url, timeout=60)
            image_response.raise_for_status()
            image_data = image_response.content

            # Register upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:person:{self.person_id}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }

            register_response = requests.post(
                'https://api.linkedin.com/v2/assets?action=registerUpload',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                },
                json=register_data
            )

            register_response.raise_for_status()
            register_result = register_response.json()
            
            upload_url = register_result['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            asset_urn = register_result['value']['asset']

            # Upload image data
            upload_response = requests.post(
                upload_url,
                headers={
                    'Authorization': f'Bearer {self.access_token}'
                },
                data=image_data
            )

            upload_response.raise_for_status()
            
            logger.info(f"Successfully uploaded image to LinkedIn: {asset_urn}")
            return asset_urn

        except Exception as e:
            logger.error(f"LinkedIn image upload failed: {str(e)}")
            raise

    async def _upload_video(self, video_url: str) -> str:
        """Upload video to LinkedIn and return asset URN"""
        try:
            # Download video
            video_response = requests.get(video_url, timeout=300)  # 5 minute timeout
            video_response.raise_for_status()
            video_data = video_response.content

            # Register upload
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                    "owner": f"urn:li:person:{self.person_id}",
                    "serviceRelationships": [
                        {
                            "relationshipType": "OWNER",
                            "identifier": "urn:li:userGeneratedContent"
                        }
                    ]
                }
            }

            register_response = requests.post(
                'https://api.linkedin.com/v2/assets?action=registerUpload',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                },
                json=register_data
            )

            register_response.raise_for_status()
            register_result = register_response.json()
            
            upload_url = register_result['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
            asset_urn = register_result['value']['asset']

            # Upload video data
            upload_response = requests.post(
                upload_url,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'video/mp4'
                },
                data=video_data
            )

            upload_response.raise_for_status()
            
            logger.info(f"Successfully uploaded video to LinkedIn: {asset_urn}")
            return asset_urn

        except Exception as e:
            logger.error(f"LinkedIn video upload failed: {str(e)}")
            raise

    def _is_video_url(self, url: str) -> bool:
        """Check if URL points to a video file"""
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        return any(url.lower().endswith(ext) for ext in video_extensions)

    def _is_image_url(self, url: str) -> bool:
        """Check if URL points to an image file"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return any(url.lower().endswith(ext) for ext in image_extensions)

    def _has_credentials(self) -> bool:
        """Check if all required credentials are available"""
        return all([self.access_token, self.person_id])

    async def get_post_analytics(self, post_id: str) -> Dict:
        """Get analytics for a LinkedIn post"""
        try:
            # LinkedIn analytics require specific permissions and are limited
            response = requests.get(
                f'https://api.linkedin.com/v2/socialActions/{post_id}',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'X-Restli-Protocol-Version': '2.0.0'
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'platform': 'linkedin',
                    'post_id': post_id,
                    'likes': data.get('likesSummary', {}).get('totalLikes', 0),
                    'comments': data.get('commentsSummary', {}).get('totalComments', 0),
                    'shares': data.get('sharesSummary', {}).get('totalShares', 0)
                }
            else:
                logger.warning(f"LinkedIn analytics not available for post {post_id}")
                return {
                    'platform': 'linkedin',
                    'post_id': post_id,
                    'error': 'Analytics not available'
                }

        except Exception as e:
            logger.error(f"Failed to get LinkedIn analytics for {post_id}: {str(e)}")
            raise

    async def delete_post(self, post_id: str) -> bool:
        """Delete a LinkedIn post"""
        try:
            response = requests.delete(
                f'https://api.linkedin.com/v2/ugcPosts/{post_id}',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'X-Restli-Protocol-Version': '2.0.0'
                }
            )

            if response.status_code == 204:
                logger.info(f"Successfully deleted LinkedIn post {post_id}")
                return True
            else:
                logger.warning(f"Failed to delete LinkedIn post {post_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting LinkedIn post {post_id}: {str(e)}")
            return False

    async def get_profile_info(self) -> Dict:
        """Get LinkedIn profile information"""
        try:
            response = requests.get(
                'https://api.linkedin.com/v2/people/(id:' + self.person_id + ')',
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'X-Restli-Protocol-Version': '2.0.0'
                }
            )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get LinkedIn profile info: {str(e)}")
            raise
