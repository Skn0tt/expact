"""
demo docstring
"""

import json
import os
import subprocess
import pwd
import platform
from typing import Callable, Optional
import urllib.parse
import re

import pandas
import requests
import scipy.stats

from datapact.schema import (
    Line,
    DataframeTestEvaluationResult,
    SeriesTestEvaluationResult,
)


def compute(value):
    if "compute" in dir(value):
        return value.compute()
    return value


def line_to_markdown(line: Line) -> str:
    if line.success:
        return f"✅ {line.type}"
    return f"❌ {line.type}: {line.message}"


class Expectation:
    def __init__(
        self,
        asserter: "Asserter",
        name: str,
        execute_callable: Callable[[Line], None],
        meta: dict,
    ):
        self.name = name
        self.asserter = asserter
        self.execute_callable = execute_callable
        self.meta = meta

    def execute(self):
        line = Line(self.name, critical=self.asserter.critical, meta=self.meta)
        self.execute_callable(line)
        return line

    def _repr_markdown_(self):
        line = self.execute()
        return line_to_markdown(line)


def get_login():
    return pwd.getpwuid(os.getuid())[0]


def get_session_fingerprint() -> str:
    return urllib.parse.quote(f"{get_login()}@{platform.node()}", safe="")


def get_github_url() -> Optional[str]:
    originUrlP = subprocess.run(
        ["git", "remote", "get-url", "origin"], check=False, capture_output=True
    )
    if originUrlP.returncode != 0:
        return None

    originUrl = originUrlP.stdout.decode("utf-8").strip()
    match = re.search(r"git@github\.com:(.*)\/(.*)\.git", originUrl)
    if match is None:
        return None
    org = match.group(1)
    repo = match.group(2)

    refP = subprocess.run(
        ["git", "show", "-s", "--format=%H"], check=True, capture_output=True
    )
    ref = refP.stdout.decode("utf-8").strip()

    url = f"https://github.com/{org}/{repo}/tree/{ref}"

    isClean = (
        subprocess.run(
            ["git", "diff", "--exit-code"], check=False, capture_output=True
        ).returncode
        == 0
    )
    if not isClean:
        url += "#dirty"

    return url


class SeriesTest:
    """
    wraps a column
    """

    def __init__(self, parent: "DataframeTest", series: pandas.Series):
        self.parent = parent
        self.series = series
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self.unit: Optional[str] = None
        self.should = Asserter(series, critical=False)
        self.must = Asserter(series, critical=True)

    def describe(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        unit: Optional[str] = None,
    ):
        """
        demo docstring
        """
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if unit is not None:
            self.unit = unit
        return self

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        return self


class Asserter:
    def __init__(self, series: pandas.Series, critical: bool):
        for base in self.__class__.__bases__:
            if hasattr(base, "__init__"):
                base.__init__(self)

        self.series = series
        self.critical = critical
        self.expectations: "list[Expectation]" = []

    def record(
        self,
        _type: str,
        execute: Callable[["Line"], None],
        meta: dict = {},
    ) -> Expectation:
        expectation = Expectation(self, _type, execute, meta)
        self.expectations.append(expectation)
        return expectation

    def bins(self):
        bins = pandas.cut(self.series, bins=10).value_counts()
        return json.loads(bins.to_json())

    def be_normal(self, alpha: float = 0.05):
        """
        performs a normaltest.

        uses `scipy.stats.normaltest` under the hood.

        Args:
            alpha :
                sensitivity of the test. low value = more sensitive.

        Examples:
            >>> de.salary.should.be_normal(alpha=0.1)
        """

        def execute(line: Line):
            stat, p = scipy.stats.normaltest(self.series)
            line.set("stat", stat)
            line.set("p", p)
            line.set("bins", self.bins())
            if p < alpha:
                line.fail(f"not normal. p={p}, stat={stat}")

        return self.record("be_normal", execute, {"alpha": alpha})

    def be_between(self, minimum: float, maximum: float):
        """
        checks the value range.

        Args:
            minimum :
                if there's a value lower than this, it will fail.
            maximum :
                if there's a value higher than this, it will fail.

        Examples:
            >>> de.age.should.be_between(0, 150)
        """

        def execute(line: Line):
            found_min = compute(self.series.min())
            found_max = compute(self.series.max())

            line.set("found_minimum", found_min)
            line.set("found_maximum", found_max)

            extends_left = found_min < minimum
            extends_right = found_max > maximum

            if extends_left and extends_right:
                line.fail(
                    f"out of range. expected to be in $({minimum}, {maximum})$ \n"
                    + f"but found $({found_min}, {found_max})$."
                )
            elif extends_left:
                line.fail(
                    f"expected values to be at least ${minimum}$, but found ${found_min}$"
                )
            elif extends_right:
                line.fail(
                    f"expected values to be at most ${maximum}$, but found ${found_max}$"
                )

        return self.record(
            "be_between", execute, {"minimum": minimum, "maximum": maximum}
        )

    def be_positive(self):
        """
        checks if all values are 0 or higher.

        Examples:
            >>> de.age.should.be_positive()
        """

        def execute(line: Line):
            found_min = compute(self.series.min())

            line.set("min", found_min)

            if found_min < 0:
                line.fail(f"negative value found: min is {found_min}")

        return self.record("be_positive", execute)

    def be_negative(self):
        """
        checks if all values are 0 or smaller.

        Examples:
            >>> de.debt.should.be_negative()
        """

        def execute(line: Line):
            found_max = self.series.max()

            line.set("max", found_max)

            if found_max < 0:
                line.fail(f"positive value found: max is {found_max}")

        return self.record("be_negative", execute)

    def not_be_null(self):
        """
        checks if there are any null values.

        Examples:
            >>> de.user_id.must.not_be_null()
        """

        def execute(line: Line):
            if self.series.isnull().values.any():
                line.fail("found null values")

        return self.record("not_be_null", execute)

    def be_one_of(self, *_args):
        """
        checks if there's any value not in the given list.

        Examples:
            >>> de.state.must.be_one_of("active", "sleeping", "inactive")
        """

        def execute(line: Line):
            raise Exception("not implemented")

        return self.record("be_one_of", execute)


# pylint: disable=too-many-instance-attributes
class DataframeTest:
    """
    some demo doc
    """

    def __init__(self, dataframe: pandas.DataFrame):
        self.dataframe = dataframe
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self.url: Optional[str] = get_github_url()
        self.series_tests: "dict[str, SeriesTest]" = {}
        self.server: Optional[str] = None
        self.token: Optional[str] = None
        super().__init__()

    def connect(self, server: str = "datafox.dev", token: Optional[str] = None):
        if "://" not in server:
            server = "https://" + server
        self.server = server
        self.token = token

    def is_connected(self):
        return self.token is not None

    def upload(self, result: DataframeTestEvaluationResult):
        requests.put(
            f"{self.server}/api/v1/testruns/{get_session_fingerprint()}",
            headers={"Authorization": f"Bearer {self.token}"},
            json=result.to_dict(),  # pyright: reportGeneralTypeIssues=false
        )

    def describe(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
    ):
        """
        demo docstring
        """
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if url is not None:
            self.url = url
        return self

    def get_series_test(self, series: pandas.Series):
        if not series.name in self.series_tests:
            self.series_tests[series.name] = SeriesTest(self, series)
        return self.series_tests[series.name]

    def __getattr__(self, attr) -> SeriesTest:
        if not attr in self.dataframe.columns:
            raise AttributeError
        series = self.dataframe[attr]
        return self.get_series_test(series)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        return self

    def evaluate(self) -> DataframeTestEvaluationResult:
        """
        Runs all tests on the dataframe.
        If connected, uploads results.
        Returns a JSON representation of the results. (TODO: make this a real JSON)
        """

        result = DataframeTestEvaluationResult(self.title, self.description, self.url)

        for series_test in self.series_tests.values():
            series_result = SeriesTestEvaluationResult(
                series_test.series.name,
                series_test.title,
                series_test.description,
                series_test.unit,
            )
            result.series.append(series_result)

            for asserter in [series_test.should, series_test.must]:
                for expectation in asserter.expectations:
                    line = expectation.execute()
                    series_result.lines.append(line)

        if self.is_connected():
            self.upload(result)

        return result

    def __repr__(self):
        return self._repr_markdown_()

    def _repr_markdown_(self):
        """
        see https://ipython.readthedocs.io/en/stable/config/integrating.html#rich-display
        """
        result = self.evaluate()

        md = ""

        for series in result.series:
            md += f"**{series.name}**  \n"
            for line in series.lines:
                md += line_to_markdown(line)
                md += "  \n"
            md += "\n"

        return md


def test(dataframe: pandas.DataFrame):
    """
    demo docstring
    """
    return DataframeTest(dataframe)
