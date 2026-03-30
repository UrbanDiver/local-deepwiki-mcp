"""SearchConfigResolver -- config resolution extracted from SearchEngine.

Centralises the mutable configuration state (default profile, adaptive flag,
fuzzy helper) and the resolution logic that turns a ``SearchRequest`` into
concrete execution parameters (mode, profile, min-similarity, fetch-limit).

Extracting this into its own class reduces ``SearchEngine`` from 22 methods
down to ~14, keeping it below the god-class threshold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from local_deepwiki.logging import get_logger

from .schema import (
    SEARCH_PROFILES,
    SearchProfile,
    SearchProfileConfig,
)

if TYPE_CHECKING:
    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

    from .cache import AdaptiveSearcher
    from .mixins.search_types import SearchRequest

logger = get_logger(__name__)


class SearchConfigResolver:
    """Resolves search configuration from requests and mutable defaults.

    Owns the mutable config state that ``SearchEngine`` previously held
    (default profile, adaptive search flag, fuzzy helper) and provides
    pure-logic resolution methods that translate a ``SearchRequest`` into
    concrete execution parameters.

    Args:
        default_search_profile: Default search profile enum.
        adaptive_search_enabled: Whether adaptive depth estimation is on.
        default_search_mode: Default search mode string.
        adaptive_searcher: Adaptive search depth estimator.
    """

    def __init__(
        self,
        *,
        default_search_profile: SearchProfile = SearchProfile.BALANCED,
        adaptive_search_enabled: bool = True,
        default_search_mode: str = "vector",
        adaptive_searcher: "AdaptiveSearcher",
    ) -> None:
        self._default_search_profile = default_search_profile
        self._adaptive_search_enabled = adaptive_search_enabled
        self._default_search_mode = default_search_mode
        self._adaptive_searcher = adaptive_searcher

        # Lazily initialised fuzzy search helper
        self._fuzzy_search_helper: "FuzzySearchHelper | None" = None

    # -- property accessors for mutable config ---------------------------------

    @property
    def default_search_profile(self) -> SearchProfile:
        return self._default_search_profile

    @default_search_profile.setter
    def default_search_profile(self, value: SearchProfile) -> None:
        self._default_search_profile = value

    @property
    def adaptive_search_enabled(self) -> bool:
        return self._adaptive_search_enabled

    @adaptive_search_enabled.setter
    def adaptive_search_enabled(self, value: bool) -> None:
        self._adaptive_search_enabled = value

    @property
    def fuzzy_search_helper(self) -> "FuzzySearchHelper | None":
        return self._fuzzy_search_helper

    @fuzzy_search_helper.setter
    def fuzzy_search_helper(self, value: "FuzzySearchHelper | None") -> None:
        self._fuzzy_search_helper = value

    @property
    def default_search_mode(self) -> str:
        return self._default_search_mode

    # -----------------------------------------------------------------
    # Fuzzy helper (lazy init)
    # -----------------------------------------------------------------

    async def get_fuzzy_helper(self, store: Any) -> "FuzzySearchHelper":
        """Get or create the fuzzy search helper.

        Args:
            store: The VectorStore instance (needed by FuzzySearchHelper).

        Returns:
            FuzzySearchHelper instance with built name index.
        """
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        if self._fuzzy_search_helper is None:
            self._fuzzy_search_helper = FuzzySearchHelper(store)

        if not self._fuzzy_search_helper.is_built:
            await self._fuzzy_search_helper.build_name_index()

        return self._fuzzy_search_helper

    # -----------------------------------------------------------------
    # Resolution methods
    # -----------------------------------------------------------------

    def resolve_search_profile(
        self, profile: SearchProfile | str | None
    ) -> tuple[SearchProfile, SearchProfileConfig]:
        """Resolve a profile argument to a ``(SearchProfile, ProfileConfig)`` pair."""
        if profile is None:
            resolved = self._default_search_profile
        elif isinstance(profile, str):
            try:
                resolved = SearchProfile(profile.lower())
            except ValueError:
                logger.warning("Invalid search profile '%s', using default", profile)
                resolved = self._default_search_profile
        else:
            resolved = profile
        return resolved, SEARCH_PROFILES[resolved]

    def resolve_search_config(
        self, request: "SearchRequest"
    ) -> tuple[str, SearchProfile, SearchProfileConfig, float]:
        """Resolve effective search mode, profile, and min similarity from request."""
        from .search_engine import resolve_search_mode

        effective_mode = resolve_search_mode(
            request.search_mode, self._default_search_mode
        )
        resolved_profile, profile_config = self.resolve_search_profile(request.profile)
        effective_min_similarity = (
            request.min_similarity
            if request.min_similarity is not None
            else profile_config.min_similarity
        )
        return (
            effective_mode,
            resolved_profile,
            profile_config,
            effective_min_similarity,
        )

    def compute_fetch_limit(
        self,
        request: "SearchRequest",
        profile_config: SearchProfileConfig,
    ) -> int:
        """Compute the number of candidates to fetch before post-processing."""
        base_multiplier = profile_config.fetch_multiplier
        needs_extra = bool(request.path_pattern or request.use_fuzzy)
        if needs_extra:
            base_multiplier = max(base_multiplier, 3.0)
        if self._adaptive_search_enabled:
            adaptive_depth = self._adaptive_searcher.estimate_optimal_depth(
                request.query, request.limit
            )
            fetch_limit = max(int(request.limit * base_multiplier), adaptive_depth)
        else:
            fetch_limit = int(request.limit * base_multiplier)
        return min(fetch_limit, profile_config.rerank_candidates)
