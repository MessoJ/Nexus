import os
import logging
from typing import Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

class YouTubePublisher:
    def __init__(self):
        self.client_id = os.getenv('YOUTUBE_CLIENT_ID')
        self.client_secret = os.getenv('YOUTUBE_CLIENT_SECRET')
        self.refresh_token = os.getenv('YOUTUBE_REFRESH_TOKEN')
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            logger.warning("YouTube credentials not fully configured")

    async def publish(self, content: Dict) -> Dict:
        """Publish video content to YouTube"""
        try:
            if not self._has_credentials():
                raise ValueError("YouTube credentials not configured")

            # Build YouTube service
            youtube = self._build_service()
            
            # Prepare video metadata
            video_metadata = {
                'snippet': {
                    'title': content['title'][:100],  # YouTube title limit
                    'description': content.get('description', '')[:5000],  # Description limit
                    'tags': content.get('tags', [])[:10],  # Max 10 tags
                    'categoryId': '22',  # People & Blogs category
                    'defaultLanguage': 'en'
                },
                'status': {
                    'privacyStatus': 'public',  # or 'private', 'unlisted'
                    'selfDeclaredMadeForKids': False
                }
            }

            # Download video file
            video_url = content.get('video_url') or content.get('media_url')
            if not video_url:
                raise ValueError("No video URL provided for YouTube upload")

            video_file = await self._download_media(video_url)
            
            # Upload video
            media = MediaIoBaseUpload(
                BytesIO(video_file),
                mimetype='video/mp4',
                resumable=True
            )

            request = youtube.videos().insert(
                part=','.join(video_metadata.keys()),
                body=video_metadata,
                media_body=media
            )

            response = self._execute_upload(request)
            
            # Set custom thumbnail if provided
            if content.get('thumbnail_url'):
                try:
                    await self._upload_thumbnail(youtube, response['id'], content['thumbnail_url'])
                except Exception as e:
                    logger.warning(f"Failed to upload thumbnail: {str(e)}")

            video_url = f"https://www.youtube.com/watch?v={response['id']}"
            
            logger.info(f"Successfully uploaded to YouTube: {video_url}")
            
            return {
                'platform': 'youtube',
                'url': video_url,
                'video_id': response['id'],
                'status': 'published',
                'published_at': response.get('snippet', {}).get('publishedAt')
            }

        except Exception as e:
            logger.error(f"YouTube publishing failed: {str(e)}")
            raise

    def _has_credentials(self) -> bool:
        """Check if all required credentials are available"""
        return all([self.client_id, self.client_secret, self.refresh_token])

    def _build_service(self):
        """Build YouTube API service with credentials"""
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Refresh the token
        credentials.refresh(Request())
        
        return build(
            self.api_service_name,
            self.api_version,
            credentials=credentials
        )

    def _execute_upload(self, request):
        """Execute resumable upload with retry logic"""
        response = None
        error = None
        retry = 0
        max_retries = 3

        while response is None and retry < max_retries:
            try:
                status, response = request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        return response
                    else:
                        raise Exception(f"Upload failed: {response}")
            except Exception as e:
                error = e
                retry += 1
                logger.warning(f"Upload attempt {retry} failed: {str(e)}")

        if response is None:
            raise Exception(f"Upload failed after {max_retries} retries: {str(error)}")

        return response

    async def _download_media(self, url: str) -> bytes:
        """Download media file from URL"""
        try:
            response = requests.get(url, timeout=300)  # 5 minute timeout
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download media from {url}: {str(e)}")
            raise

    async def _upload_thumbnail(self, youtube, video_id: str, thumbnail_url: str):
        """Upload custom thumbnail to YouTube video"""
        try:
            thumbnail_data = await self._download_media(thumbnail_url)
            
            media = MediaIoBaseUpload(
                BytesIO(thumbnail_data),
                mimetype='image/jpeg',
                resumable=True
            )

            youtube.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()

            logger.info(f"Thumbnail uploaded for video {video_id}")

        except Exception as e:
            logger.error(f"Thumbnail upload failed for {video_id}: {str(e)}")
            raise

    async def get_video_analytics(self, video_id: str) -> Dict:
        """Get analytics data for a YouTube video"""
        try:
            youtube = self._build_service()
            
            # Get video statistics
            response = youtube.videos().list(
                part='statistics,snippet',
                id=video_id
            ).execute()

            if not response['items']:
                raise ValueError(f"Video {video_id} not found")

            video_data = response['items'][0]
            stats = video_data.get('statistics', {})
            snippet = video_data.get('snippet', {})

            return {
                'platform': 'youtube',
                'video_id': video_id,
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'published_at': snippet.get('publishedAt'),
                'title': snippet.get('title'),
                'duration': snippet.get('duration')
            }

        except Exception as e:
            logger.error(f"Failed to get YouTube analytics for {video_id}: {str(e)}")
            raise

    async def update_video(self, video_id: str, updates: Dict) -> Dict:
        """Update video metadata"""
        try:
            youtube = self._build_service()
            
            # Get current video data
            current = youtube.videos().list(
                part='snippet,status',
                id=video_id
            ).execute()

            if not current['items']:
                raise ValueError(f"Video {video_id} not found")

            video_data = current['items'][0]
            
            # Update fields
            if 'title' in updates:
                video_data['snippet']['title'] = updates['title'][:100]
            if 'description' in updates:
                video_data['snippet']['description'] = updates['description'][:5000]
            if 'tags' in updates:
                video_data['snippet']['tags'] = updates['tags'][:10]
            if 'privacy_status' in updates:
                video_data['status']['privacyStatus'] = updates['privacy_status']

            # Update video
            response = youtube.videos().update(
                part='snippet,status',
                body=video_data
            ).execute()

            logger.info(f"Updated YouTube video {video_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to update YouTube video {video_id}: {str(e)}")
            raise

    def get_oauth_url(self, redirect_uri: str) -> str:
        """Get OAuth authorization URL for YouTube"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = redirect_uri
        
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url
