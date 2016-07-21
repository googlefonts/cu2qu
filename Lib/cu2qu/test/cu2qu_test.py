# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import print_function, division, absolute_import

import collections
import unittest
import random

from cu2qu import curve_to_quadratic, curves_to_quadratic, curve_spline_dist
from cu2qu.benchmark import generate_curve

MAX_ERR = 5


class CurveToQuadraticTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Do the curve conversion ahead of time, and run tests on results."""

        random.seed(1)
        curves = [generate_curve() for i in range(1000)]
        cls.single_splines = [
            curve_to_quadratic(c, MAX_ERR) for c in curves]
        cls.single_errors = [
            curve_spline_dist(c, s) for c, s in zip(curves, cls.single_splines)]

        curve_groups = [curves[i:i + 3] for i in range(0, 300, 3)]
        cls.compat_splines = [
            curves_to_quadratic(c, [MAX_ERR] * 3) for c in curve_groups]
        cls.compat_errors = [
            [curve_spline_dist(c, s) for c, s in zip(curve_group, splines)]
            for curve_group, splines in zip(curve_groups, cls.compat_splines)]

        cls.results = []

    @classmethod
    def tearDownClass(cls):
        """Print stats from conversion, as determined during tests."""

        for tag, results in cls.results:
            print('\n%s\n%s' % (
                tag, '\n'.join(
                    '%s: %s (%d)' % (k, '#' * (v // 10 + 1), v)
                    for k, v in sorted(results.items()))))

    def test_results_unchanged(self):
        """Tests that the results of conversion haven't changed since the time
        of this test's writing. Useful as a quick check whenever one modifies
        the conversion algorithm.
        """

        expected = {
            3: 6,
            4: 26,
            5: 82,
            6: 232,
            7: 360,
            8: 266,
            9: 28}

        results = collections.defaultdict(int)
        for spline in self.single_splines:
            n = len(spline) - 1
            results[n] += 1
        self.assertEqual(results, expected)
        self.results.append(('single spline lengths', results))

    def test_results_unchanged_multiple(self):
        """Test that conversion results are unchanged for multiple curves."""

        expected = {
            6: 11,
            7: 35,
            8: 49,
            9: 5}

        results = collections.defaultdict(int)
        for splines in self.compat_splines:
            n = len(splines[0]) - 1
            for spline in splines[1:]:
                self.assertEqual(len(spline) - 1, n,
                    'Got incompatible conversion results')
            results[n] += 1
        self.assertEqual(results, expected)
        self.results.append(('compatible spline lengths', results))

    def test_does_not_exceed_tolerance(self):
        """Test that conversion results do not exceed given error tolerance."""

        results = collections.defaultdict(int)
        for error in self.single_errors:
            results[round(error, 1)] += 1
            self.assertLessEqual(error, MAX_ERR)
        self.results.append(('single errors', results))

    def test_does_not_exceed_tolerance_multiple(self):
        """Test that error tolerance isn't exceeded for multiple curves."""

        results = collections.defaultdict(int)
        for errors in self.compat_errors:
            for error in errors:
                results[round(error, 1)] += 1
                self.assertLessEqual(error, MAX_ERR)
        self.results.append(('compatible errors', results))


if __name__ == '__main__':
    unittest.main()
