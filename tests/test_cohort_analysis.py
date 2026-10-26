"""Unit tests for src/cohort_analysis.py."""

from __future__ import annotations

import pandas as pd
import pytest

from src.cohort_analysis import (build_cohort_table, cohort_summary,
                                 retention_matrix)


@pytest.fixture()
def cohort_frame(synthetic_orders):
    return build_cohort_table(synthetic_orders)


class TestBuildCohortTable:
    def test_cohort_assignment_first_order_month(self, cohort_frame):
        # c1's first purchase is Jan-2018, c2's is Jan-2018, c3 Feb, c4 Mar
        cohorts = cohort_frame.groupby("cohort_month")["cohort_size"].first()
        assert cohorts[pd.Timestamp("2018-01-01")] == 2  # c1 + c2
        assert cohorts[pd.Timestamp("2018-02-01")] == 1  # c3
        assert cohorts[pd.Timestamp("2018-03-01")] == 1  # c4

    def test_month_zero_is_100_pct(self, cohort_frame):
        m0 = cohort_frame[cohort_frame["months_since_first"] == 0]
        assert (m0["retention_pct"] == 100.0).all()
        assert (m0["active_customers"] == m0["cohort_size"]).all()

    def test_repeat_month_detected(self, cohort_frame):
        # c1 ordered again in Feb => Jan cohort month-1 active = 1 of 2
        row = cohort_frame[
            (cohort_frame["cohort_month"] == pd.Timestamp("2018-01-01"))
            & (cohort_frame["months_since_first"] == 1)].iloc[0]
        assert row["active_customers"] == 1
        assert row["retention_pct"] == 50.0

    def test_no_future_zero_fill(self, cohort_frame):
        # Mar-2018 cohort cannot have a month-2 row (data ends Apr-2018 but
        # c4 simply had no Apr order -> row exists only if there was activity)
        mar = cohort_frame[cohort_frame["cohort_month"]
                           == pd.Timestamp("2018-03-01")]
        assert mar["months_since_first"].max() == 0  # c4 never returned

    def test_active_customers_never_exceeds_size(self, cohort_frame):
        assert (cohort_frame["active_customers"]
                <= cohort_frame["cohort_size"]).all()

    def test_retention_bounds(self, cohort_frame):
        assert cohort_frame["retention_pct"].between(0, 100).all()


class TestRetentionMatrix:
    def test_shape_and_values(self, cohort_frame):
        mat = retention_matrix(cohort_frame)
        assert mat.loc["2018-01", 0] == 100.0
        assert mat.loc["2018-01", 1] == 50.0
        # missing cells stay NaN (never zero-filled)
        assert pd.isna(mat.loc["2018-03", 1])


class TestCohortSummary:
    def test_observed_only(self, cohort_frame):
        s = cohort_summary(cohort_frame)
        assert (s["months_since_first"] >= 0).all()
        row = s[s["months_since_first"] == 0].iloc[0]
        assert row["avg_retention_pct"] == 100.0
