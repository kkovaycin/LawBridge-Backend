from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


class YouTubeCommentError(RuntimeError):
    pass


class YouTubeConfigurationError(YouTubeCommentError):
    pass


@dataclass(frozen=True)
class YouTubeComment:
    id: str
    author: str | None
    text: str
    published_at: str | None
    like_count: int


def extract_youtube_video_id(value: str) -> str | None:
    stripped = value.strip()
    if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(stripped):
        return stripped

    for match in YOUTUBE_URL_PATTERN.finditer(value):
        parsed = urlparse(match.group(0).rstrip(".,;:)]}"))
        host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
        path_parts = [part for part in parsed.path.split("/") if part]

        if host == "youtu.be" and path_parts:
            candidate = path_parts[0]
            if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate):
                return candidate

        if host.endswith("youtube.com"):
            query_video_id = parse_qs(parsed.query).get("v", [None])[0]
            if query_video_id and YOUTUBE_VIDEO_ID_PATTERN.fullmatch(query_video_id):
                return query_video_id

            if path_parts and path_parts[0] in {"embed", "shorts", "live"} and len(path_parts) > 1:
                candidate = path_parts[1]
                if YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate):
                    return candidate

    return None


class YouTubeCommentClient:
    endpoint = "https://www.googleapis.com/youtube/v3/commentThreads"

    def __init__(
        self,
        api_key: str | None,
        max_comments: int,
        timeout_seconds: int,
    ) -> None:
        self.api_key = api_key.strip() if api_key else None
        self.max_comments = max_comments
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def fetch_video_comments(self, video_id: str) -> list[YouTubeComment]:
        if not self.api_key:
            raise YouTubeConfigurationError(
                "YouTube video linkinden yorum cekmek icin YOUTUBE_API_KEY ayarlanmalidir."
            )

        comments: list[YouTubeComment] = []
        page_token: str | None = None

        while len(comments) < self.max_comments:
            page_size = min(100, self.max_comments - len(comments))
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": page_size,
                "order": "relevance",
                "textFormat": "plainText",
                "key": self.api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                response = requests.get(self.endpoint, params=params, timeout=self.timeout_seconds)
            except requests.RequestException as exc:
                raise YouTubeCommentError(f"YouTube yorumlari cekilemedi: {exc}") from exc

            if response.status_code != 200:
                raise YouTubeCommentError(self._error_message(response))

            payload = response.json()
            for item in payload.get("items", []):
                comment = self._parse_comment(item)
                if comment and comment.text.strip():
                    comments.append(comment)

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        if not comments:
            raise YouTubeCommentError("Bu video icin okunabilir YouTube yorumu bulunamadi.")

        return comments

    @staticmethod
    def _parse_comment(item: dict[str, Any]) -> YouTubeComment | None:
        snippet = item.get("snippet", {})
        top_level = snippet.get("topLevelComment", {})
        comment_id = top_level.get("id") or item.get("id")
        comment_snippet = top_level.get("snippet", {})
        text = comment_snippet.get("textOriginal") or comment_snippet.get("textDisplay") or ""

        if not comment_id or not text:
            return None

        return YouTubeComment(
            id=str(comment_id),
            author=comment_snippet.get("authorDisplayName"),
            text=str(text).strip(),
            published_at=comment_snippet.get("publishedAt"),
            like_count=int(comment_snippet.get("likeCount") or 0),
        )

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
            errors = payload.get("error", {}).get("errors", [])
            reason = errors[0].get("reason") if errors else None
            message = payload.get("error", {}).get("message")
        except ValueError:
            reason = None
            message = response.text

        if reason == "commentsDisabled":
            return "Bu videoda yorumlar kapali oldugu icin analiz yapilamadi."

        if reason in {"forbidden", "quotaExceeded", "dailyLimitExceeded"}:
            return f"YouTube API yorumu reddetti veya kota doldu: {message or reason}"

        if response.status_code == 403:
            return f"YouTube API erisim hatasi: {message or 'API anahtarini ve kotayi kontrol edin.'}"

        return f"YouTube yorumlari cekilemedi ({response.status_code}): {message or response.text}"
