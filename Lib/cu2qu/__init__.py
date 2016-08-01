# Copyright 2015 Google Inc. All Rights Reserved.
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

__all__ = ['curve_to_quadratic', 'curves_to_quadratic']

MAX_N = 100


class Cu2QuError(Exception):
    pass


class ApproxNotFoundError(Cu2QuError):
    def __init__(self, curve):
        message = "no approximation found: %s" % curve
        super(Cu2QuError, self).__init__(message)
        self.curve = curve


def dot(v1, v2):
    """Return the dot product of two vectors."""
    return (v1 * v2.conjugate()).real


def calc_cubic_points(a, b, c, d):
    _1 = d
    _2 = (c / 3.0) + d
    _3 = (b + c) / 3.0 + _2
    _4 = a + d + c + b
    return _1, _2, _3, _4


def calc_cubic_parameters(p0, p1, p2, p3):
    c = (p1 - p0) * 3.0
    b = (p2 - p1) * 3.0 - c
    d = p0
    a = p3 - d - c - b
    return a, b, c, d


def split_cubic_into_n(p0, p1, p2, p3, n):
    # Hand-coded special-cases
    if n == 2:
        return split_cubic_into_two(p0, p1, p2, p3)
    if n == 3:
        return split_cubic_into_three(p0, p1, p2, p3)

    a, b, c, d = calc_cubic_parameters(p0, p1, p2, p3)
    segments = []
    dt = 1 / n
    delta_2 = dt * dt
    delta_3 = dt * delta_2
    for i in range(n):
        t1 = i * dt
        t1_2 = t1 * t1
        t1_3 = t1 * t1_2
        # calc new a, b, c and d
        a1 = a * delta_3
        b1 = (3*a*t1 + b) * delta_2
        c1 = (2*b*t1 + c + 3*a*t1_2) * dt
        d1 = a*t1_3 + b*t1_2 + c*t1 + d
        segments.append(calc_cubic_points(a1, b1, c1, d1))
    return segments


def split_cubic_into_two(p0, p1, p2, p3):
    mid = (p0 + 3 * (p1 + p2) + p3) * .125
    deriv3 = (p3 + p2 - p1 - p0) * .125
    return ((p0, (p0 + p1) * .5, mid - deriv3, mid),
            (mid, mid + deriv3, (p2 + p3) * .5, p3))


def split_cubic_into_three(p0, p1, p2, p3, _27=1/27):
    # we define 1/27 as a keyword argument so that it will be evaluated only
    # once but still in the scope of this function
    mid1 = (8*p0 + 12*p1 + 6*p2 + p3) * _27
    deriv1 = (p3 + 3*p2 - 4*p0) * _27
    mid2 = (p0 + 6*p1 + 12*p2 + 8*p3) * _27
    deriv2 = (4*p3 - 3*p1 - p0) * _27
    return ((p0, (2*p0 + p1) / 3, mid1 - deriv1, mid1),
            (mid1, mid1 + deriv1, mid2 - deriv2, mid2),
            (mid2, mid2 + deriv2, (p2 + 2*p3) / 3, p3))


def cubic_approx_control(p, t):
    """Approximate a cubic bezier curve with a quadratic one.
       Returns the candidate control point."""

    p1 = p[0] + (p[1] - p[0]) * 1.5
    p2 = p[3] + (p[2] - p[3]) * 1.5
    return p1 + (p2 - p1) * t


def calc_intersect(a, b, c, d):
    """Calculate the intersection of ab and cd, given a, b, c, d."""

    ab = b - a
    cd = d - c
    p = ab * 1j
    try:
        h = dot(p, a - c) / dot(p, cd)
    except ZeroDivisionError:
        return None
    return c + cd * h


def cubic_farthest_fit_inside(p0, p1, p2, p3, tolerance):
    """Returns True if the cubic Bezier p entirely lies within a distance
    tolerance of origin, False otherwise.  Assumes that p0 and p3 do fit
    within tolerance of origin, and just checks the inside of the curve."""

    # First check p2 then p1, as p2 has higher error early on.
    if abs(p2) <= tolerance and abs(p1) <= tolerance:
        return True

    # Split.
    mid = (p0 + 3 * (p1 + p2) + p3) * .125
    if abs(mid) > tolerance:
        return False
    deriv3 = (p3 + p2 - p1 - p0) * .125
    return (cubic_farthest_fit_inside(p0, (p0+p1)*.5, mid-deriv3, mid, tolerance) and
            cubic_farthest_fit_inside(mid, mid+deriv3, (p2+p3)*.5, p3, tolerance))


def cubic_approx_spline(cubic, n, tolerance, _2_3=2/3):
    """Approximate a cubic bezier curve with a spline of n quadratics.

    Returns None if no quadratic approximation is found which lies entirely
    within a distance `tolerance` from the original curve.
    """
    # we define 2/3 as a keyword argument so that it will be evaluated only
    # once but still in the scope of this function

    if n == 1:
        # Try the uniq quadratic approximating cubic that maintains
        # endpoint tangents.

        q1 = calc_intersect(*cubic)
        if q1 is None:
            return None
        c0 = cubic[0]
        c3 = cubic[3]
        c1 = c0 + (q1 - c0) * _2_3
        c2 = c3 + (q1 - c3) * _2_3
        if not cubic_farthest_fit_inside(0,
                                         c1 - cubic[1],
                                         c2 - cubic[2],
                                         0, tolerance):
            return None
        return c0, q1, c3

    cubics = split_cubic_into_n(cubic[0], cubic[1], cubic[2], cubic[3], n)

    # calculate the spline of quadratics and check errors at the same time.
    next_q1 = cubic_approx_control(cubics[0], 0)
    q2 = cubic[0]
    d1 = 0j
    spline = [cubic[0], next_q1]
    for i in range(1, n+1):

        # Current cubic to convert
        c0, c1, c2, c3 = cubics[i-1]

        # Current quadratic approximation of current cubic
        q0 = q2
        q1 = next_q1
        if i < n:
            next_q1 = cubic_approx_control(cubics[i], i / (n-1))
            spline.append(next_q1)
            q2 = (q1 + next_q1) * .5
        else:
            q2 = cubic[3]

        # End-point deltas
        d0 = d1
        d1 = q2 - c3

        if (abs(d1) > tolerance or
            not cubic_farthest_fit_inside(d0,
                                          q0 + (q1 - q0) * _2_3 - c1,
                                          q2 + (q1 - q2) * _2_3 - c2,
                                          d1,
                                          tolerance)):
            return None
    spline.append(cubic[3])

    return spline


def curve_to_quadratic(curve, max_err):
    """Return a quadratic spline approximating this cubic bezier.
    Raise 'ApproxNotFoundError' if no suitable approximation can be found
    with the given parameters.
    """

    curve = [complex(*p) for p in curve]

    for n in range(1, MAX_N + 1):
        spline = cubic_approx_spline(curve, n, max_err)
        if spline is not None:
            # done. go home
            return [(s.real, s.imag) for s in spline]

    raise ApproxNotFoundError(curve)



def curves_to_quadratic(curves, max_errors):
    """Return quadratic splines approximating these cubic beziers.
    Raise 'ApproxNotFoundError' if no suitable approximation can be found
    for all curves with the given parameters.
    """

    curves = [[complex(*p) for p in curve] for curve in curves]
    assert len(max_errors) == len(curves)

    for n in range(1, MAX_N + 1):
        splines = []
        for c, e in zip(curves, max_errors):
            spline = cubic_approx_spline(c, n, e)
            if spline is None:
                break
            splines.append(spline)
        else:
            # done. go home
            return [[(s.real, s.imag) for s in spline] for spline in splines]

    raise ApproxNotFoundError(curves)

