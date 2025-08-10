import os
import logging
from typing import Dict, Optional
import tweepy
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

class TwitterPublisher:
    def __init__(self):
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        
        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            logger.warning("Twitter credentials not fully configured")

    async def publish(self, content: Dict) -> Dict:
        """Publish content to Twitter"""
        try:
            if not self._has_credentials():
                raise ValueError("Twitter credentials not configured")

            # Initialize Twitter API v2 client
            client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=True
            )

            # Initialize API v1.1 for media upload
            auth = tweepy.OAuth1UserHandler(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_token_secret
            )
            api_v1 = tweepy.API(auth)

            # Prepare tweet text
            tweet_text = content.get('text', content.get('title', ''))
            
            # Add hashtags if they fit
            hashtags = content.get('hashtags', [])
            if hashtags:
                hashtag_text = ' ' + ' '.join(hashtags[:3])  # Max 3 hashtags
                if len(tweet_text + hashtag_text) <= 280:
                    tweet_text += hashtag_text

            # Ensure tweet is within character limit
            if len(tweet_text) > 280:
                tweet_text = tweet_text[:277] + "..."

            media_ids = []
            
            # Upload media if provided
            media_url = content.get('media_url')
            if media_url:
                try:
                    media_id = await self._upload_media(api_v1, media_url)
                    if media_id:
                        media_ids.append(media_id)
                except Exception as e:
                    logger.warning(f"Failed to upload media to Twitter: {str(e)}")

            # Post tweet
            tweet_params = {'text': tweet_text}
            if media_ids:
                tweet_params['media_ids'] = media_ids

            response = client.create_tweet(**tweet_params)
            
            tweet_id = response.data['id']
            tweet_url = f"https://twitter.com/user/status/{tweet_id}"
            
            logger.info(f"Successfully posted to Twitter: {tweet_url}")
            
            return {
                'platform': 'twitter',
                'url': tweet_url,
                'tweet_id': tweet_id,
                'status': 'published',
                'text': tweet_text
            }

        except Exception as e:
            logger.error(f"Twitter publishing failed: {str(e)}")
            raise

    async def publish_thread(self, content: Dict) -> Dict:
        """Publish a Twitter thread for longer content"""
        try:
            if not self._has_credentials():
                raise ValueError("Twitter credentials not configured")

            client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                wait_on_rate_limit=True
            )

            # Split content into thread
            full_text = content.get('text', content.get('title', ''))
            thread_tweets = self._split_into_thread(full_text)
            
            tweet_ids = []
            previous_tweet_id = None
            
            for i, tweet_text in enumerate(thread_tweets):
                tweet_params = {'text': tweet_text}
                
                if previous_tweet_id:
                    tweet_params['in_reply_to_tweet_id'] = previous_tweet_id
                
                response = client.create_tweet(**tweet_params)
                tweet_id = response.data['id']
                tweet_ids.append(tweet_id)
                previous_tweet_id = tweet_id
                
                logger.info(f"Posted thread tweet {i+1}/{len(thread_tweets)}: {tweet_id}")

            main_tweet_url = f"https://twitter.com/user/status/{tweet_ids[0]}"
            
            return {
                'platform': 'twitter',
                'url': main_tweet_url,
                'tweet_ids': tweet_ids,
                'status': 'published',
                'thread_length': len(tweet_ids)
            }

        except Exception as e:
            logger.error(f"Twitter thread publishing failed: {str(e)}")
            raise

    def _split_into_thread(self, text: str, max_length: int = 270) -> list:
        """Split long text into Twitter thread"""
        if len(text) <= max_length:
            return [text]
        
        sentences = text.split('. ')
        tweets = []
        current_tweet = ""
        
        for sentence in sentences:
            # Add thread numbering for tweets after the first
            thread_prefix = f"{len(tweets) + 1}/ " if tweets else ""
            test_tweet = thread_prefix + current_tweet + sentence + ". "
            
            if len(test_tweet) <= max_length:
                current_tweet += sentence + ". "
            else:
                if current_tweet:
                    final_tweet = (f"{len(tweets) + 1}/ " if tweets else "") + current_tweet.strip()
                    tweets.append(final_tweet)
                current_tweet = sentence + ". "
        
        if current_tweet:
            final_tweet = (f"{len(tweets) + 1}/ " if tweets else "") + current_tweet.strip()
            tweets.append(final_tweet)
        
        return tweets

    async def _upload_media(self, api_v1, media_url: str) -> Optional[str]:
        """Upload media to Twitter"""
        try:
            # Download media
            response = requests.get(media_url, timeout=60)
            response.raise_for_status()
            
            media_data = BytesIO(response.content)
            
            # Determine media type
            content_type = response.headers.get('content-type', '').lower()
            
            if 'image' in content_type:
                media = api_v1.media_upload(filename="image.jpg", file=media_data)
                return media.media_id
            elif 'video' in content_type:
                # For video, we need chunked upload
                media = api_v1.media_upload(filename="video.mp4", file=media_data, chunked=True)
                return media.media_id
            else:
                logger.warning(f"Unsupported media type for Twitter: {content_type}")
                return None
                
        except Exception as e:
            logger.error(f"Media upload to Twitter failed: {str(e)}")
            return None

    def _has_credentials(self) -> bool:
        """Check if all required credentials are available"""
        return all([
            self.api_key, 
            self.api_secret, 
            self.access_token, 
            self.access_token_secret
        ])

    async def get_tweet_analytics(self, tweet_id: str) -> Dict:
        """Get analytics for a specific tweet"""
        try:
            client = tweepy.Client(bearer_token=self.bearer_token)
            
            tweet = client.get_tweet(
                tweet_id,
                tweet_fields=['public_metrics', 'created_at', 'author_id'],
                expansions=['author_id']
            )
            
            if not tweet.data:
                raise ValueError(f"Tweet {tweet_id} not found")
            
            metrics = tweet.data.public_metrics
            
            return {
                'platform': 'twitter',
                'tweet_id': tweet_id,
                'retweets': metrics.get('retweet_count', 0),
                'likes': metrics.get('like_count', 0),
                'replies': metrics.get('reply_count', 0),
                'quotes': metrics.get('quote_count', 0),
                'created_at': str(tweet.data.created_at),
                'author_id': tweet.data.author_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get Twitter analytics for {tweet_id}: {str(e)}")
            raise

    async def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet"""
        try:
            client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            
            response = client.delete_tweet(tweet_id)
            
            if response.data.get('deleted'):
                logger.info(f"Successfully deleted tweet {tweet_id}")
                return True
            else:
                logger.warning(f"Failed to delete tweet {tweet_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting tweet {tweet_id}: {str(e)}")
            return False

    async def schedule_tweet(self, content: Dict, schedule_time: str) -> Dict:
        """Schedule a tweet for future posting (requires Twitter API v2 with scheduling)"""
        # Note: Tweet scheduling requires Twitter API v2 with specific access levels
        # This is a placeholder for the scheduling functionality
        logger.info(f"Tweet scheduling requested for {schedule_time}")
        
        return {
            'platform': 'twitter',
            'status': 'scheduled',
            'scheduled_time': schedule_time,
            'content': content.get('text', '')[:50] + '...'
        }
