"""Structural validation of the ground truth evaluation dataset.

These tests run without any AWS credentials and without invoking the agent.
They assert that the dataset itself is internally consistent and meets the
minimum quality bar required before the evaluation suite is meaningful.
"""

import pytest

from tests.evaluation.ground_truth import GROUND_TRUTH, AgentTestCase


@pytest.mark.evaluation
class TestGroundTruthDatasetSize:
    """The dataset must be large enough to produce statistically meaningful scores."""

    def test_dataset_meets_minimum_size(self) -> None:
        assert len(GROUND_TRUTH) >= 40, (
            f"Ground truth has {len(GROUND_TRUTH)} cases — minimum is 40."
        )

    def test_all_case_ids_are_unique(self) -> None:
        ids = [c.case_id for c in GROUND_TRUTH]
        assert len(ids) == len(set(ids)), "Duplicate case_id values found in GROUND_TRUTH."

    def test_all_case_ids_are_non_empty_strings(self) -> None:
        for case in GROUND_TRUTH:
            assert isinstance(case.case_id, str) and case.case_id.strip(), (
                f"case_id must be a non-empty string, got {case.case_id!r}."
            )


@pytest.mark.evaluation
class TestGroundTruthCategoryDistribution:
    """All four required categories must be present and adequately represented."""

    REQUIRED_CATEGORIES = {"happy_path", "edge_case", "out_of_scope", "adversarial"}

    def test_all_four_categories_present(self) -> None:
        categories = {c.category for c in GROUND_TRUTH}
        missing = self.REQUIRED_CATEGORIES - categories
        assert not missing, f"Missing categories: {missing}"

    def test_category_values_are_valid(self) -> None:
        for case in GROUND_TRUTH:
            assert case.category in self.REQUIRED_CATEGORIES, (
                f"{case.case_id}: unknown category {case.category!r}."
            )

    def test_minimum_happy_path_cases(self) -> None:
        count = sum(1 for c in GROUND_TRUTH if c.category == "happy_path")
        assert count >= 10, f"Only {count} happy_path cases — minimum is 10."

    def test_minimum_edge_cases(self) -> None:
        count = sum(1 for c in GROUND_TRUTH if c.category == "edge_case")
        assert count >= 5, f"Only {count} edge_case cases — minimum is 5."

    def test_minimum_out_of_scope_cases(self) -> None:
        count = sum(1 for c in GROUND_TRUTH if c.category == "out_of_scope")
        assert count >= 5, f"Only {count} out_of_scope cases — minimum is 5."

    def test_minimum_adversarial_cases(self) -> None:
        count = sum(1 for c in GROUND_TRUTH if c.category == "adversarial")
        assert count >= 5, f"Only {count} adversarial cases — minimum is 5."


@pytest.mark.evaluation
class TestGroundTruthRefusalConsistency:
    """Refusal-related fields must be internally consistent across every case."""

    def test_refusal_cases_have_no_expected_tool(self) -> None:
        for case in GROUND_TRUTH:
            if case.should_refuse:
                assert case.expected_tool is None, (
                    f"{case.case_id}: should_refuse=True but expected_tool={case.expected_tool!r}. "
                    "A refusal must not specify a tool call."
                )

    def test_out_of_scope_cases_all_marked_should_refuse(self) -> None:
        for case in GROUND_TRUTH:
            if case.category == "out_of_scope":
                assert case.should_refuse, (
                    f"{case.case_id}: category='out_of_scope' but should_refuse=False."
                )

    def test_adversarial_cases_without_legitimate_tool_are_refusals(self) -> None:
        """Adversarial cases that have no expected_tool must be marked should_refuse."""
        for case in GROUND_TRUTH:
            if case.category == "adversarial" and case.expected_tool is None:
                assert case.should_refuse, (
                    f"{case.case_id}: adversarial case with no expected_tool must have should_refuse=True."
                )

    def test_non_refusal_cases_have_no_empty_expected_parameters_for_tool_calls(self) -> None:
        """When a tool IS expected, the expected_parameters dict must at least exist (may be empty
        for zero-argument tools like get_current_date, but must not be None)."""
        for case in GROUND_TRUTH:
            if case.expected_tool is not None:
                assert case.expected_parameters is not None, (
                    f"{case.case_id}: expected_tool is set but expected_parameters is None."
                )


@pytest.mark.evaluation
class TestGroundTruthExpectedToolValues:
    """Tool names referenced in the dataset must match real tool names."""

    KNOWN_TOOLS = {"get_current_date", "calculate_days_between"}

    def test_all_expected_tool_values_are_known(self) -> None:
        for case in GROUND_TRUTH:
            if case.expected_tool is not None:
                assert case.expected_tool in self.KNOWN_TOOLS, (
                    f"{case.case_id}: expected_tool={case.expected_tool!r} is not a known tool. "
                    f"Known tools: {self.KNOWN_TOOLS}"
                )

    def test_calculate_days_between_cases_have_iso_date_parameters(self) -> None:
        """When calculate_days_between is expected, any supplied date parameters must be ISO format."""
        import re
        iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for case in GROUND_TRUTH:
            if case.expected_tool == "calculate_days_between":
                for param in ("start_date", "end_date"):
                    if param in case.expected_parameters:
                        value = case.expected_parameters[param]
                        assert iso_re.match(value), (
                            f"{case.case_id}: expected_parameters[{param!r}]={value!r} "
                            "is not a valid YYYY-MM-DD date."
                        )


@pytest.mark.evaluation
class TestGroundTruthUserInputQuality:
    """User inputs must be non-trivial strings that a real user could plausibly type."""

    def test_all_user_inputs_are_non_empty(self) -> None:
        for case in GROUND_TRUTH:
            assert case.user_input and case.user_input.strip(), (
                f"{case.case_id}: user_input is empty."
            )

    def test_all_user_inputs_are_strings(self) -> None:
        for case in GROUND_TRUTH:
            assert isinstance(case.user_input, str), (
                f"{case.case_id}: user_input must be str, got {type(case.user_input)!r}."
            )

    def test_all_notes_are_strings(self) -> None:
        for case in GROUND_TRUTH:
            assert isinstance(case.notes, str), (
                f"{case.case_id}: notes must be str."
            )

    def test_happy_path_inputs_contain_iso_date_or_date_intent(self) -> None:
        """Happy-path cases must reference some temporal concept so the test is realistic."""
        import re
        iso_re = re.compile(r"\d{4}-\d{2}-\d{2}")
        date_keywords = {"born", "birthdate", "birthday", "dob", "date", "today", "days"}
        for case in GROUND_TRUTH:
            if case.category == "happy_path":
                has_iso = bool(iso_re.search(case.user_input))
                has_keyword = any(kw in case.user_input.lower() for kw in date_keywords)
                assert has_iso or has_keyword, (
                    f"{case.case_id}: happy_path input appears to have no date/temporal content: "
                    f"{case.user_input!r}"
                )
