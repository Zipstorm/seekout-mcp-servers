import pytest

from seekout_mcp_search.query_builder import QueryBuilder, flat_params_to_filters


class TestFlatParamsToFilters:
    """Test the flat parameter adapter."""

    def test_empty_params(self):
        assert flat_params_to_filters() == {}

    def test_titles_parsed(self):
        result = flat_params_to_filters(titles="Staff Engineer, Senior Engineer")
        assert result == {
            "current_title": {"alt_names": ["Staff Engineer", "Senior Engineer"]}
        }

    def test_companies_parsed(self):
        result = flat_params_to_filters(companies="Google, Meta")
        assert result == {
            "current_company": {"alt_names": ["Google", "Meta"]}
        }

    def test_locations_parsed(self):
        result = flat_params_to_filters(locations="Seattle, San Francisco")
        assert result == {
            "location": {"alt_names": ["Seattle", "San Francisco"]}
        }

    def test_skills_stored_as_internal_key(self):
        result = flat_params_to_filters(skills="Python, AWS")
        assert result == {"_skill_names": ["Python", "AWS"]}

    def test_years_experience_both(self):
        result = flat_params_to_filters(years_experience_min=5, years_experience_max=15)
        assert result == {"years_of_experience": {"min": 5, "max": 15}}

    def test_years_experience_min_only(self):
        result = flat_params_to_filters(years_experience_min=3)
        assert result == {"years_of_experience": {"min": 3}}

    def test_all_params_combined(self):
        result = flat_params_to_filters(
            titles="Engineer",
            companies="Google",
            locations="Seattle",
            skills="Python",
            years_experience_min=5,
        )
        assert "current_title" in result
        assert "current_company" in result
        assert "location" in result
        assert "_skill_names" in result
        assert "years_of_experience" in result

    def test_empty_strings_ignored(self):
        result = flat_params_to_filters(titles="", companies="  ,  , ")
        assert result == {}

    def test_whitespace_trimmed(self):
        result = flat_params_to_filters(titles="  Engineer  ,  Manager  ")
        assert result == {
            "current_title": {"alt_names": ["Engineer", "Manager"]}
        }


class TestQueryBuilder:
    """Test the query builder with mocked entity resolution."""

    @pytest.mark.asyncio
    async def test_build_simple_query(self, query_builder):
        result = await query_builder.build(query="Python engineer")

        assert result["search"] == "Python engineer"
        assert result["top"] == 10
        assert result["skip"] == 0
        assert result["index"] == "NorthAmerica"

    @pytest.mark.asyncio
    async def test_build_with_top_clamped(self, query_builder):
        result = await query_builder.build(query="test", top=100)
        assert result["top"] == 25

    @pytest.mark.asyncio
    async def test_build_with_skip_clamped(self, query_builder):
        result = await query_builder.build(query="test", skip=-5)
        assert result["skip"] == 0

    @pytest.mark.asyncio
    async def test_build_with_facet_fields(self, query_builder):
        result = await query_builder.build(
            query="test",
            facet_fields=["cur_company_id", "skills"],
        )
        assert result["facets"] == [
            {"facet_type": "cur_company_id", "count": 10},
            {"facet_type": "skills", "count": 10},
        ]

    @pytest.mark.asyncio
    async def test_build_with_entity_resolution(self, mock_seekout_api, entity_resolver):
        mock_seekout_api.search_entities.return_value = [
            {"text": "Google", "id": 60, "count": 150000}
        ]
        builder = QueryBuilder(entity_resolver)

        result = await builder.build(
            query="engineer",
            filters={"current_company": {"alt_names": ["Google"]}},
        )

        assert "filters" in result
        assert result["filters"]["current_company"]["ids"] == [60]

    @pytest.mark.asyncio
    async def test_build_with_unresolved_entity(self, mock_seekout_api, entity_resolver):
        mock_seekout_api.search_entities.return_value = [
            {"text": "Apple Inc", "id": 10, "count": 100000},
            {"text": "Apple Leisure Group", "id": 11, "count": 80000},
        ]
        builder = QueryBuilder(entity_resolver)

        result = await builder.build(
            query="engineer",
            filters={"current_company": {"alt_names": ["Apple"]}},
        )

        assert "filters" in result
        assert result["filters"]["current_company"]["alt_names"] == ["Apple"]

    @pytest.mark.asyncio
    async def test_build_skills_appended_to_search(self, mock_seekout_api, entity_resolver):
        mock_seekout_api.search_entities.return_value = [
            {"text": "Python", "id": 42, "count": 500000}
        ]
        builder = QueryBuilder(entity_resolver)

        result = await builder.build(
            query="engineer",
            filters={"_skill_names": ["Python"]},
        )

        assert "skill:42" in result["search"]
        assert "engineer AND skill:42" == result["search"]

    @pytest.mark.asyncio
    async def test_build_unresolved_skills_quoted(self, mock_seekout_api, entity_resolver):
        mock_seekout_api.search_entities.return_value = []
        builder = QueryBuilder(entity_resolver)

        result = await builder.build(
            query="engineer",
            filters={"_skill_names": ["data science"]},
        )

        assert '"data science"' in result["search"]

    @pytest.mark.asyncio
    async def test_build_multiple_skills(self, mock_seekout_api, entity_resolver):
        mock_seekout_api.search_entities.side_effect = [
            [{"text": "Python", "id": 42, "count": 500000}],
            [],  # "data science" unresolved
        ]
        builder = QueryBuilder(entity_resolver)

        result = await builder.build(
            query="engineer",
            filters={"_skill_names": ["Python", "data science"]},
        )

        assert 'engineer AND (skill:42 OR "data science")' == result["search"]

    @pytest.mark.asyncio
    async def test_build_skills_only_no_query(self, mock_seekout_api, entity_resolver):
        mock_seekout_api.search_entities.return_value = [
            {"text": "Python", "id": 42, "count": 500000}
        ]
        builder = QueryBuilder(entity_resolver)

        result = await builder.build(
            query="",
            filters={"_skill_names": ["Python"]},
        )

        assert result["search"] == "skill:42"

    @pytest.mark.asyncio
    async def test_build_yoe_filter_passthrough(self, query_builder):
        result = await query_builder.build(
            query="test",
            filters={"years_of_experience": {"min": 5, "max": 15}},
        )

        assert result["filters"]["years_of_experience"] == {"min": 5, "max": 15}
