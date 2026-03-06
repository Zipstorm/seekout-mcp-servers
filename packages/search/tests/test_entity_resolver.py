import pytest

from seekout_mcp_search.entity_resolver import EntityResolver


class TestSelectBestMatch:
    """Test the static confidence matching logic."""

    def test_exact_match_wins_even_when_not_highest_count(self):
        results = [
            {"text": "Amazon Web Services", "id": 101, "count": 50000},
            {"text": "AWS", "id": 100, "count": 5000},
        ]
        result = EntityResolver._select_best_match(results, "AWS")
        assert result == {"name": "AWS", "id": 100, "resolved": True}

    def test_exact_match_case_insensitive(self):
        results = [
            {"text": "Google", "id": 60, "count": 150000},
            {"text": "Google Cloud", "id": 8842, "count": 12000},
        ]
        result = EntityResolver._select_best_match(results, "google")
        assert result == {"name": "google", "id": 60, "resolved": True}

    def test_clear_winner_when_no_exact_match(self):
        results = [
            {"text": "Microsoft", "id": 1, "count": 200000},
            {"text": "Microsoft Azure", "id": 2, "count": 30000},
        ]
        result = EntityResolver._select_best_match(results, "MSFT")
        assert result == {"name": "MSFT", "id": 1, "resolved": True}

    def test_ambiguous_no_clear_winner(self):
        results = [
            {"text": "Apple Inc", "id": 10, "count": 100000},
            {"text": "Apple Leisure Group", "id": 11, "count": 80000},
        ]
        result = EntityResolver._select_best_match(results, "Apple")
        assert result == {"name": "Apple", "id": None, "resolved": False}

    def test_single_result_always_resolves(self):
        results = [{"text": "Startup XYZ", "id": 999, "count": 50}]
        result = EntityResolver._select_best_match(results, "Startup")
        assert result == {"name": "Startup", "id": 999, "resolved": True}

    def test_empty_results_unresolved(self):
        result = EntityResolver._select_best_match([], "Nothing")
        assert result == {"name": "Nothing", "id": None, "resolved": False}


class TestResolve:
    """Test the async resolve method with caching."""

    @pytest.mark.asyncio
    async def test_resolve_single_name(self, mock_seekout_api):
        mock_seekout_api.search_entities.return_value = [
            {"text": "Google", "id": 60, "count": 150000}
        ]
        resolver = EntityResolver(mock_seekout_api)

        results = await resolver.resolve("Company", ["Google"])

        assert len(results) == 1
        assert results[0] == {"name": "Google", "id": 60, "resolved": True}

    @pytest.mark.asyncio
    async def test_resolve_multiple_names_in_parallel(self, mock_seekout_api):
        mock_seekout_api.search_entities.side_effect = [
            [{"text": "Google", "id": 60, "count": 150000}],
            [{"text": "Meta", "id": 492, "count": 80000}],
        ]
        resolver = EntityResolver(mock_seekout_api)

        results = await resolver.resolve("Company", ["Google", "Meta"])

        assert len(results) == 2
        assert results[0]["resolved"] is True
        assert results[1]["resolved"] is True
        assert mock_seekout_api.search_entities.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self, mock_seekout_api):
        mock_seekout_api.search_entities.return_value = [
            {"text": "Google", "id": 60, "count": 150000}
        ]
        resolver = EntityResolver(mock_seekout_api)

        # First call
        await resolver.resolve("Company", ["Google"])
        # Second call — should use cache
        await resolver.resolve("Company", ["Google"])

        assert mock_seekout_api.search_entities.call_count == 1

    @pytest.mark.asyncio
    async def test_api_error_returns_unresolved(self, mock_seekout_api):
        mock_seekout_api.search_entities.side_effect = Exception("API error")
        resolver = EntityResolver(mock_seekout_api)

        results = await resolver.resolve("Company", ["Google"])

        assert len(results) == 1
        assert results[0] == {"name": "Google", "id": None, "resolved": False}
