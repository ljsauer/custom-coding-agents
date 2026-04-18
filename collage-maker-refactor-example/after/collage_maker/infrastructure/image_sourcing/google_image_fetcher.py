"""
GoogleImageFetcher — Stealth Infrastructure Adapter

Implements IReferenceImageSource by scraping Google Images with advanced
anti-detection measures, dynamic timing, and robust error handling.

This stealth-oriented version addresses common blocking issues:
- Dynamic request timing with jitter to avoid predictable patterns
- User-Agent rotation with realistic browser headers  
- Session rotation and lifecycle management
- Adaptive rate limiting with exponential backoff
- Optional proxy support with automatic failover
- Request pattern obfuscation and header randomization
- Comprehensive logging for debugging and monitoring
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from random import choice, uniform, randint, shuffle
from typing import Optional
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup

from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.reference_image_source import (
    IReferenceImageSource,
    ImageQuality,
    ImageLicense,
    ImageResult,
    ImageMetadata,
)

logger = logging.getLogger(__name__)

# Base configuration
_GOOGLE_IMAGE_SEARCH_BASE_URL = "https://www.google.com/search"
_MIN_IMAGE_SIZE_BYTES = 2048  # 2KB minimum
_VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}

# Dynamic timing ranges (seconds)
_REQUEST_TIMEOUT_RANGE = (10, 20)
_REQUEST_DELAY_RANGE = (1.0, 5.0)
_RETRY_BASE_DELAY_RANGE = (2.0, 4.0)
_SESSION_LIFETIME_RANGE = (50, 100)  # requests per session

# Realistic User-Agent pool with recent versions
_USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Realistic Accept-Language variations
_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8",
    "en-GB,en-US;q=0.9,en;q=0.8",
    "en-US,en;q=0.5",
]


@dataclass
class StealthConfig:
    """Configuration for anti-detection measures."""
    enable_proxy_rotation: bool = False
    proxy_list: list[str] = field(default_factory=list)
    max_failures_before_session_reset: int = 3
    adaptive_backoff_multiplier: float = 1.5
    max_backoff_seconds: float = 60.0
    randomize_image_sizes: bool = True
    vary_search_parameters: bool = True


class GoogleImageFetcher(IReferenceImageSource):
    """Stealth Google Images scraper with advanced anti-detection."""

    def __init__(
        self, 
        images_per_keyword: int = 4,
        stealth_config: Optional[StealthConfig] = None
    ) -> None:
        self._images_per_keyword = max(1, min(images_per_keyword, 20))
        self._stealth_config = stealth_config or StealthConfig()
        
        # Session management
        self._session: Optional[requests.Session] = None
        self._session_request_count = 0
        self._session_max_requests = randint(*_SESSION_LIFETIME_RANGE)
        
        # Adaptive rate limiting state
        self._consecutive_failures = 0
        self._current_delay_multiplier = 1.0
        self._proxy_index = 0
        
        logger.info(
            f"GoogleImageFetcher initialized (images_per_keyword={self._images_per_keyword}, "
            f"proxy_rotation={self._stealth_config.enable_proxy_rotation})"
        )

    def fetch_for_keyword(
        self,
        keyword: Keyword,
        min_quality: ImageQuality = ImageQuality.MEDIUM,
        required_license: ImageLicense = ImageLicense.ANY,
        max_results: int | None = None,
    ) -> list[ImageResult]:
        """Fetch images with stealth measures and adaptive behavior."""
        max_results = min(max_results or self._images_per_keyword, 50)
        
        logger.info(
            f"Fetching images for keyword '{keyword.text}' "
            f"(max_results={max_results}, quality={min_quality.name})"
        )

        try:
            search_terms = self._get_search_terms(keyword)
            all_results = []

            for i, search_term in enumerate(search_terms):
                if len(all_results) >= max_results:
                    break
                    
                logger.debug(f"Trying search term {i+1}/{len(search_terms)}: '{search_term}'")
                
                # Dynamic delay between requests
                if i > 0:
                    delay = uniform(*_REQUEST_DELAY_RANGE) * self._current_delay_multiplier
                    logger.debug(f"Waiting {delay:.1f}s between requests")
                    time.sleep(delay)

                # Ensure fresh session
                self._ensure_session_health()

                results = self._scrape_images_with_adaptive_retry(
                    search_term, min_quality, required_license
                )
                
                if results:
                    logger.info(f"Found {len(results)} images for '{search_term}'")
                    all_results.extend(results)
                    self._consecutive_failures = 0  # Reset failure count on success
                    self._current_delay_multiplier = max(1.0, self._current_delay_multiplier * 0.9)
                else:
                    logger.warning(f"No images found for '{search_term}'")
                    self._consecutive_failures += 1

            unique_results = self._deduplicate_results(all_results)[:max_results]
            
            logger.info(
                f"Returning {len(unique_results)} unique images for keyword '{keyword.text}'"
            )
            
            return unique_results

        except Exception as e:
            logger.error(f"Failed to fetch images for keyword '{keyword.text}': {e}")
            return []

    def get_source_name(self) -> str:
        """Return human-readable name of this image source."""
        return "Google Images (Stealth)"

    def is_available(self) -> bool:
        """Check availability with proper session management."""
        try:
            self._ensure_session_health()
            response = self._session.get(
                "https://www.google.com/", 
                timeout=uniform(*_REQUEST_TIMEOUT_RANGE)
            )
            is_available = response.status_code == 200
            logger.info(f"Google Images availability check: {'OK' if is_available else 'FAILED'}")
            return is_available
        except Exception as e:
            logger.warning(f"Google Images availability check failed: {e}")
            return False

    def get_rate_limit_info(self) -> dict[str, int]:
        """Get conservative rate limiting information."""
        # Reduced estimates for stealth operation
        return {
            "requests_per_hour": 50,  # Conservative for stealth
            "requests_remaining": max(0, 50 - self._session_request_count),
            "reset_time": 3600,
        }

    # ------------------------------------------------------------------
    # Session and stealth management
    # ------------------------------------------------------------------

    def _ensure_session_health(self) -> None:
        """Ensure session is healthy and rotate if needed."""
        should_rotate = (
            self._session is None or
            self._session_request_count >= self._session_max_requests or
            self._consecutive_failures >= self._stealth_config.max_failures_before_session_reset
        )
        
        if should_rotate:
            logger.debug("Rotating session for stealth")
            self._rotate_session()

    def _rotate_session(self) -> None:
        """Create a new session with randomized configuration."""
        if self._session:
            self._session.close()
            
        self._session = self._create_stealth_session()
        self._session_request_count = 0
        self._session_max_requests = randint(*_SESSION_LIFETIME_RANGE)
        
        # Reset failure-related state
        if self._consecutive_failures >= self._stealth_config.max_failures_before_session_reset:
            self._consecutive_failures = 0
            self._current_delay_multiplier = 1.0

    def _create_stealth_session(self) -> requests.Session:
        """Create session with anti-detection headers and configuration."""
        session = requests.Session()
        
        # Randomize core headers
        user_agent = choice(_USER_AGENTS)
        accept_language = choice(_ACCEPT_LANGUAGES)
        
        # Base headers that mimic real browser behavior
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }
        
        # Add browser-specific headers
        if "Chrome" in user_agent:
            headers.update({
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"' if "Windows" in user_agent else '"macOS"',
            })
        
        session.headers.update(headers)
        
        # Configure proxy if enabled
        if self._stealth_config.enable_proxy_rotation and self._stealth_config.proxy_list:
            proxy = self._get_next_proxy()
            if proxy:
                session.proxies.update({
                    'http': proxy,
                    'https': proxy
                })
                logger.debug(f"Using proxy: {proxy}")
        
        return session

    def _get_next_proxy(self) -> Optional[str]:
        """Get next proxy from rotation list."""
        if not self._stealth_config.proxy_list:
            return None
            
        proxy = self._stealth_config.proxy_list[self._proxy_index]
        self._proxy_index = (self._proxy_index + 1) % len(self._stealth_config.proxy_list)
        return proxy

    # ------------------------------------------------------------------
    # Enhanced scraping with adaptive behavior
    # ------------------------------------------------------------------

    def _get_search_terms(self, keyword: Keyword) -> list[str]:
        """Get search terms with optional variations for stealth."""
        base_terms = [keyword.text]
        
        # Add search variants if available
        if hasattr(keyword, 'get_search_variants'):
            try:
                variants = keyword.get_search_variants()[:2]
                base_terms.extend(variants)
            except Exception as e:
                logger.debug(f"Failed to get keyword variants: {e}")
        
        # Shuffle order for unpredictability
        if self._stealth_config.vary_search_parameters:
            shuffle(base_terms)
                
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in base_terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
                
        return unique_terms[:3]

    def _scrape_images_with_adaptive_retry(
        self,
        search_term: str,
        min_quality: ImageQuality,
        required_license: ImageLicense,
    ) -> list[ImageResult]:
        """Scrape with adaptive exponential backoff and jitter."""
        
        max_retries = 3 + min(self._consecutive_failures, 2)  # Increase retries if struggling
        
        for attempt in range(max_retries):
            try:
                # Rotate User-Agent for each retry attempt
                if attempt > 0:
                    self._session.headers["User-Agent"] = choice(_USER_AGENTS)
                    
                results = self._scrape_images(search_term, min_quality, required_license)
                
                if results:
                    return results
                    
                if attempt < max_retries - 1:
                    # Adaptive exponential backoff with jitter
                    base_delay = uniform(*_RETRY_BASE_DELAY_RANGE)
                    exponential_factor = self._stealth_config.adaptive_backoff_multiplier ** attempt
                    jitter = uniform(0.5, 1.5)  # ±50% jitter
                    
                    delay = min(
                        base_delay * exponential_factor * jitter * self._current_delay_multiplier,
                        self._stealth_config.max_backoff_seconds
                    )
                    
                    logger.info(
                        f"Adaptive retry in {delay:.1f}s (attempt {attempt + 1}/{max_retries}, "
                        f"consecutive_failures={self._consecutive_failures})"
                    )
                    time.sleep(delay)
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for '{search_term}': {e}")
                
                if attempt < max_retries - 1:
                    # Force session rotation on repeated failures
                    if attempt >= 1:
                        self._rotate_session()
                    
                    delay = uniform(*_RETRY_BASE_DELAY_RANGE) * (2 ** attempt)
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed for '{search_term}'")
                    
        return []

    def _scrape_images(
        self,
        search_term: str,
        min_quality: ImageQuality,
        required_license: ImageLicense,
    ) -> list[ImageResult]:
        """Enhanced scraping with request obfuscation."""
        search_params = self._build_search_params(search_term, min_quality, required_license)
        
        url = f"{_GOOGLE_IMAGE_SEARCH_BASE_URL}?{urlencode(search_params)}"
        logger.debug(f"Searching URL: {url}")

        try:
            # Dynamic timeout and additional stealth headers
            timeout = uniform(*_REQUEST_TIMEOUT_RANGE)
            
            # Add realistic referer occasionally
            additional_headers = {}
            if randint(1, 10) <= 3:  # 30% of the time
                additional_headers["Referer"] = "https://www.google.com/"
            
            response = self._session.get(url, timeout=timeout, headers=additional_headers)
            response.raise_for_status()
            
            self._session_request_count += 1

            # Enhanced blocking detection
            response_text_lower = response.text.lower()
            blocking_indicators = [
                "blocked", "unusual traffic", "captcha", "robot", "automated",
                "suspicious activity", "too many requests", "rate limit"
            ]
            
            if any(indicator in response_text_lower for indicator in blocking_indicators):
                logger.warning("Potential blocking detected in response - triggering session rotation")
                self._consecutive_failures += 1
                self._current_delay_multiplier *= 2.0  # Increase delays aggressively
                return []
                
            soup = BeautifulSoup(response.text, "html.parser")
            results = self._extract_images_enhanced(soup, min_quality)
            
            logger.debug(f"Extracted {len(results)} image results from HTML")
            return results

        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout for search term: '{search_term}'")
            self._consecutive_failures += 1
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for '{search_term}': {e}")
            self._consecutive_failures += 1
        except Exception as e:
            logger.error(f"Unexpected error scraping '{search_term}': {e}")
            self._consecutive_failures += 1
            
        return []

    def _build_search_params(
        self, 
        search_term: str, 
        min_quality: ImageQuality, 
        required_license: ImageLicense
    ) -> dict[str, str]:
        """Build search parameters with optional randomization."""
        search_params = {
            "q": search_term,
            "tbm": "isch",
            "hl": "en",
            "safe": "active",
            "as_st": "y",
        }

        # Add license filtering if specified
        if required_license != ImageLicense.ANY:
            license_map = {
                ImageLicense.PUBLIC_DOMAIN: "fmc",
                ImageLicense.CREATIVE_COMMONS: "fc", 
                ImageLicense.ROYALTY_FREE: "f",
                ImageLicense.COMMERCIAL_USE: "fmc",
            }
            if required_license in license_map:
                search_params["as_rights"] = license_map[required_license]

        # Dynamic quality-based size filtering
        if self._stealth_config.randomize_image_sizes:
            # Occasionally vary size requirements for unpredictability
            quality_variants = {
                ImageQuality.HIGH: ["l", "xl"] if randint(1, 10) <= 7 else ["l"],
                ImageQuality.MEDIUM: ["m", "l"] if randint(1, 10) <= 3 else ["m"],
                ImageQuality.LOW: ["s", "m"] if randint(1, 10) <= 2 else ["s"],
            }
            
            if min_quality in quality_variants:
                search_params["isz"] = choice(quality_variants[min_quality])
        else:
            # Original static mapping
            if min_quality == ImageQuality.HIGH:
                search_params["isz"] = "l"
            elif min_quality == ImageQuality.MEDIUM:
                search_params["isz"] = "m"

        # Occasionally add additional search parameters for realism
        if self._stealth_config.vary_search_parameters and randint(1, 10) <= 2:
            additional_params = {
                "source": "lnms",
                "sa": "X",
                "ved": f"2ahUKEwi{randint(100000, 999999)}",  # Fake tracking parameter
            }
            search_params.update(choice(list(additional_params.items())))

        return search_params

    # ------------------------------------------------------------------
    # Enhanced image processing (unchanged core logic)
    # ------------------------------------------------------------------

    def _extract_images_enhanced(
        self, soup: BeautifulSoup, min_quality: ImageQuality
    ) -> list[ImageResult]:
        """Enhanced image extraction with multiple selector strategies."""
        results = []
        image_count = 0
        
        # Strategy 1: Look for images in various Google Images containers
        selectors_to_try = [
            "img[data-src]",  # Lazy-loaded images
            "img[src]",       # Direct images
            "div[data-tbnid] img",  # Thumbnail containers
            ".rg_i",          # Google Images specific class
            "[data-src*='http']", # Any element with data-src containing http
        ]
        
        for selector in selectors_to_try:
            if image_count >= self._images_per_keyword:
                break
                
            img_elements = soup.select(selector)
            logger.debug(f"Found {len(img_elements)} elements with selector: {selector}")
            
            for img_element in img_elements:
                if image_count >= self._images_per_keyword:
                    break
                    
                result = self._process_image_element(img_element, min_quality)
                if result:
                    results.append(result)
                    image_count += 1

        return results

    def _process_image_element(self, img_element, min_quality: ImageQuality) -> ImageResult | None:
        """Process a single image element and return ImageResult if valid."""
        try:
            # Extract image URL from various attributes
            img_url = None
            for attr in ["data-src", "src", "data-original", "data-lazy-src"]:
                url = img_element.get(attr)
                if url and url.startswith(("http", "//")):
                    if url.startswith("//"):
                        url = "https:" + url
                    img_url = url
                    break
                    
            if not img_url:
                return None
                
            # Skip Google's placeholder and icon images
            skip_patterns = [
                "data:image",
                "google.com/images/branding",
                "gstatic.com/hostedimg",
                "/images/cleardot.gif",
                "encrypted-tbn0.gstatic.com",  # Google's thumbnail service
            ]
            
            if any(pattern in img_url for pattern in skip_patterns):
                return None
                
            # Check for valid image extension
            parsed_url = urlparse(img_url)
            path_lower = parsed_url.path.lower()
            
            # Skip if no valid extension and not obviously an image URL
            if not any(path_lower.endswith(ext) for ext in _VALID_EXTENSIONS):
                if "image" not in img_url.lower() and "photo" not in img_url.lower():
                    return None

            # Fetch the image
            image_data = self._fetch_image_with_validation(img_url)
            if not image_data:
                return None

            # Create metadata
            metadata = self._create_enhanced_metadata(img_url, img_element)

            # Quality filtering
            if not self._meets_quality_requirements(metadata, min_quality):
                logger.debug(f"Image {img_url} doesn't meet quality requirements")
                return None

            return ImageResult(data=image_data, metadata=metadata)

        except Exception as e:
            logger.debug(f"Error processing image element: {e}")
            return None

    def _fetch_image_with_validation(self, url: str) -> bytes | None:
        """Fetch image with enhanced validation and stealth headers."""
        try:
            # Enhanced headers for image requests with randomization
            headers = {
                "Referer": choice([
                    "https://www.google.com/",
                    "https://images.google.com/",
                    f"https://www.google.com/search?q={randint(1000, 9999)}"
                ]),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            }
            
            # Occasionally add cache control
            if randint(1, 10) <= 3:
                headers["Cache-Control"] = choice(["no-cache", "max-age=0"])
            
            timeout = uniform(*_REQUEST_TIMEOUT_RANGE)
            
            response = self._session.get(
                url, 
                timeout=timeout,
                headers=headers,
                stream=True
            )
            response.raise_for_status()

            # Read content with size limit
            max_size = 10 * 1024 * 1024  # 10MB limit
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    logger.warning(f"Image too large, truncating: {url}")
                    break

            # Validate minimum size
            if len(content) < _MIN_IMAGE_SIZE_BYTES:
                logger.debug(f"Image too small ({len(content)} bytes): {url}")
                return None

            # Basic image format validation
            if not self._is_valid_image_data(content):
                logger.debug(f"Invalid image format: {url}")
                return None

            logger.debug(f"Successfully fetched image ({len(content)} bytes): {url}")
            return content

        except requests.exceptions.Timeout:
            logger.debug(f"Timeout fetching image: {url}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request error fetching image {url}: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error fetching image {url}: {e}")
            
        return None

    def _is_valid_image_data(self, data: bytes) -> bool:
        """Basic validation of image data by checking magic bytes."""
        if len(data) < 8:
            return False
            
        # Check for common image format signatures
        signatures = [
            b"\xFF\xD8\xFF",      # JPEG
            b"\x89PNG\r\n\x1a\n", # PNG
            b"RIFF",              # WebP (and others)
            b"BM",                # BMP
            b"GIF87a",            # GIF87a
            b"GIF89a",            # GIF89a
        ]
        
        return any(data.startswith(sig) for sig in signatures)

    def _create_enhanced_metadata(self, url: str, img_element) -> ImageMetadata:
        """Create enhanced metadata from image element."""
        # Extract basic metadata from HTML attributes
        width = 0
        height = 0
        alt_text = img_element.get("alt", "")
        
        # Try multiple ways to get dimensions
        for attr in ["width", "data-width", "w"]:
            if img_element.get(attr):
                try:
                    width = int(img_element.get(attr))
                    break
                except (ValueError, TypeError):
                    continue
                    
        for attr in ["height", "data-height", "h"]:
            if img_element.get(attr):
                try:
                    height = int(img_element.get(attr))
                    break
                except (ValueError, TypeError):
                    continue

        # Determine format from URL
        format_ext = "unknown"
        parsed_url = urlparse(url)
        if "." in parsed_url.path:
            format_ext = parsed_url.path.split(".")[-1].split("?")[0].lower()
            
        # Clean up format
        if format_ext not in {"jpg", "jpeg", "png", "webp", "bmp", "gif"}:
            format_ext = "unknown"

        return ImageMetadata(
            url=url,
            width=width,
            height=height,
            format=format_ext,
            alt_text=alt_text.strip() if alt_text else "",
            source="Google Images (Stealth)",
            license=ImageLicense.ANY,  # Can't reliably determine license from scraping
        )

    def _meets_quality_requirements(
        self, metadata: ImageMetadata, min_quality: ImageQuality
    ) -> bool:
        """Enhanced quality requirements checking."""
        if min_quality == ImageQuality.ANY:
            return True

        # Define quality thresholds (minimum pixels)
        quality_thresholds = {
            ImageQuality.LOW: 150 * 150,      # 22.5K pixels
            ImageQuality.MEDIUM: 300 * 300,   # 90K pixels  
            ImageQuality.HIGH: 600 * 600,     # 360K pixels
        }

        min_pixels = quality_thresholds.get(min_quality, 0)

        # Check resolution if available
        if metadata.width > 0 and metadata.height > 0:
            actual_pixels = metadata.width * metadata.height
            meets_requirement = actual_pixels >= min_pixels
            
            if not meets_requirement:
                logger.debug(
                    f"Image resolution {metadata.width}x{metadata.height} "
                    f"({actual_pixels} pixels) below {min_quality.name} threshold ({min_pixels})"
                )
                
            return meets_requirement

        # If no dimension info available, be more permissive for lower qualities
        fallback_allowed = min_quality in (ImageQuality.LOW, ImageQuality.MEDIUM)
        
        if fallback_allowed:
            logger.debug("No dimension info available, allowing for low/medium quality")
            
        return fallback_allowed

    def _deduplicate_results(self, results: list[ImageResult]) -> list[ImageResult]:
        """Remove duplicate results by URL."""
        seen_urls = set()
        unique_results = []
        
        for result in results:
            url = result.metadata.url
            if url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
                
        logger.debug(f"Deduplicated {len(results)} -> {len(unique_results)} results")
        return unique_results
