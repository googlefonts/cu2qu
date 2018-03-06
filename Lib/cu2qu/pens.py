from __future__ import print_function, division, absolute_import
from cu2qu import curve_to_quadratic, quadratic_to_curve
from fontTools.pens.basePen import AbstractPen, decomposeSuperBezierSegment
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.pointPen import BasePointToSegmentPen
from fontTools.pens.pointPen import ReverseContourPointPen


class BaseFilterPen(AbstractPen):

    def __init__(self, other_pen, reverse_direction=False):
        if reverse_direction:
            self.pen = ReverseContourPen(other_pen)
        else:
            self.pen = other_pen
        self.current_pt = None

    def _check_contour_is_open(self):
        if self.current_pt is None:
            raise AssertionError("moveTo is required")

    def _check_contour_is_closed(self):
        if self.current_pt is not None:
            raise AssertionError("closePath or endPath is required")

    def moveTo(self, pt):
        self._check_contour_is_closed()
        self.pen.moveTo(pt)
        self.current_pt = pt

    def lineTo(self, pt):
        self._check_contour_is_open()
        self.pen.lineTo(pt)
        self.current_pt = pt

    def qCurveTo(self, *points):
        self._check_contour_is_open()
        n = len(points)
        if n == 1:
            self.lineTo(points[0])
        elif n > 1:
            self.pen.qCurveTo(*points)
            self.current_pt = points[-1]
        else:
            raise AssertionError("illegal qcurve segment point count: %d" % n)

    def curveTo(self, *points):
        self._check_contour_is_open()
        n = len(points)
        if n == 1:
            self.lineTo(points[0])
        elif n == 2:
            self.qCurveTo(*points)
        elif n > 2:
            self.pen.curveTo(*points)
            self.current_pt = points[-1]
        else:
            raise AssertionError("illegal curve segment point count: %d" % n)

    def closePath(self):
        self._check_contour_is_open()
        self.pen.closePath()
        self.current_pt = None

    def endPath(self):
        self._check_contour_is_open()
        self.pen.endPath()
        self.current_pt = None

    def addComponent(self, glyphName, transformation):
        self._check_contour_is_closed()
        self.pen.addComponent(glyphName, transformation)


class Cu2QuPen(BaseFilterPen):
    """ A filter pen to convert cubic bezier curves to quadratic b-splines
    using the FontTools SegmentPen protocol.

    other_pen: another SegmentPen used to draw the transformed outline.
    max_err: maximum approximation error in font units.
    reverse_direction: flip the contours' direction but keep starting point.
    stats: a dictionary counting the point numbers of quadratic segments.
    """

    def __init__(self, other_pen, max_err, reverse_direction=False,
                 stats=None):
        super(Cu2QuPen, self).__init__(other_pen, reverse_direction)
        self.max_err = max_err
        self.stats = stats

    def _curve_to_quadratic(self, pt1, pt2, pt3):
        curve = (self.current_pt, pt1, pt2, pt3)
        quadratic = curve_to_quadratic(curve, self.max_err)
        if self.stats is not None:
            n = str(len(quadratic) - 2)
            self.stats[n] = self.stats.get(n, 0) + 1
        self.qCurveTo(*quadratic[1:])

    def curveTo(self, *points):
        self._check_contour_is_open()
        n = len(points)
        if n == 3:
            # this is the most common case, so we special-case it
            self._curve_to_quadratic(*points)
        elif n > 3:
            for segment in decomposeSuperBezierSegment(points):
                self._curve_to_quadratic(*segment)
        elif n == 2:
            self.qCurveTo(*points)
        elif n == 1:
            self.lineTo(points[0])
        else:
            raise AssertionError("illegal curve segment point count: %d" % n)


class Qu2CuPen(BaseFilterPen):
    """ A filter pen to convert quadratic b-splines curves to cubic bezier
    curves using the FontTools SegmentPen protocol.

    other_pen: another SegmentPen used to draw the transformed outline.
    reverse_direction: flip the contours' direction but keep starting point.
    """

    def _quadratic_to_curve(self, *points):
        curve = quadratic_to_curve((self.current_pt,) + points)
        self.curveTo(*curve[1:])

    def qCurveTo(self, *points):
        self._check_contour_is_open()
        n = len(points)
        if n == 1:
            self.lineTo(points[0])
        elif n > 1:
            self._quadratic_to_curve(*points)
        else:
            raise AssertionError("illegal qcurve segment point count: %d" % n)


class BaseFilterPointPen(BasePointToSegmentPen):

    def __init__(self, other_point_pen, reverse_direction=False):
        super(BaseFilterPointPen, self).__init__()
        if reverse_direction:
            self.pen = ReverseContourPointPen(other_point_pen)
        else:
            self.pen = other_point_pen

    def _flushContour(self, segments):
        assert len(segments) >= 1
        closed = segments[0][0] != "move"
        new_segments = self._filter_segments(segments)
        if closed:
            # the BasePointToSegmentPen.endPath method that calls _flushContour
            # rotates the point list of closed contours so that they end with
            # the first on-curve point. We restore the original starting point.
            new_segments = new_segments[-1:] + new_segments[:-1]
        self._drawPoints(new_segments)

    def _filter_segments(self, segments):
        return segments  # no-op

    @staticmethod
    def _split_super_bezier_segments(points):
        sub_segments = []
        # n is the number of control points
        n = len(points) - 1
        if n == 2:
            # a simple bezier curve segment
            sub_segments.append(points)
        elif n > 2:
            # a "super" bezier; decompose it
            on_curve, smooth, name, kwargs = points[-1]
            num_sub_segments = n - 1
            for i, sub_points in enumerate(decomposeSuperBezierSegment([
                    pt for pt, _, _, _ in points])):
                new_segment = []
                for point in sub_points[:-1]:
                    new_segment.append((point, False, None, {}))
                if i == (num_sub_segments - 1):
                    # the last on-curve keeps its original attributes
                    new_segment.append((on_curve, smooth, name, kwargs))
                else:
                    # on-curves of sub-segments are always "smooth"
                    new_segment.append((sub_points[-1], True, None, {}))
                sub_segments.append(new_segment)
        else:
            raise AssertionError(
                "expected 2 control points, found: %d" % n)
        return sub_segments

    def _drawPoints(self, segments):
        pen = self.pen
        pen.beginPath()
        last_offcurves = []
        for i, (segment_type, points) in enumerate(segments):
            if segment_type in ("move", "line"):
                assert len(points) == 1, (
                    "illegal line segment point count: %d" % len(points))
                pt, smooth, name, kwargs = points[0]
                pen.addPoint(pt, segment_type, smooth, name, **kwargs)
            elif segment_type in ("qcurve", "curve"):
                if segment_type == "qcurve":
                    assert len(points) >= 2, (
                        "illegal qcurve segment point count: %d" % len(points))
                else:
                    assert len(points) >= 3, (
                        "illegal curve segment point count: %d" % len(points))
                offcurves = points[:-1]
                if offcurves:
                    if i == 0:
                        # any off-curve points preceding the first on-curve
                        # will be appended at the end of the contour
                        last_offcurves = offcurves
                    else:
                        for (pt, smooth, name, kwargs) in offcurves:
                            pen.addPoint(pt, None, smooth, name, **kwargs)
                pt, smooth, name, kwargs = points[-1]
                if pt is None:
                    # special quadratic contour with no on-curve points:
                    # we need to skip the "None" point. See also the Pen
                    # protocol's qCurveTo() method and fontTools.pens.basePen
                    pass
                else:
                    pen.addPoint(pt, segment_type, smooth, name, **kwargs)
            else:
                raise AssertionError(
                    "unexpected segment type: %r" % segment_type)
        for (pt, smooth, name, kwargs) in last_offcurves:
            pen.addPoint(pt, None, smooth, name, **kwargs)
        pen.endPath()

    def addComponent(self, baseGlyphName, transformation):
        assert self.currentPath is None
        self.pen.addComponent(baseGlyphName, transformation)


class Cu2QuPointPen(BaseFilterPointPen):
    """ A filter pen to convert cubic bezier curves to quadratic b-splines
    using the RoboFab PointPen protocol.

    other_point_pen: another PointPen used to draw the transformed outline.
    max_err: maximum approximation error in font units.
    reverse_direction: reverse the winding direction of all contours.
    stats: a dictionary counting the point numbers of quadratic segments.
    """

    def __init__(self, other_point_pen, max_err, reverse_direction=False,
                 stats=None):
        super(Cu2QuPointPen, self).__init__(other_point_pen, reverse_direction)
        self.max_err = max_err
        self.stats = stats

    def _filter_segments(self, segments):
        new_segments = []
        prev_points = segments[-1][1]
        prev_on_curve = prev_points[-1][0]
        for segment_type, points in segments:
            if segment_type == 'curve':
                for sub_points in self._split_super_bezier_segments(points):
                    on_curve, smooth, name, kwargs = sub_points[-1]
                    bcp1, bcp2 = sub_points[0][0], sub_points[1][0]
                    cubic = [prev_on_curve, bcp1, bcp2, on_curve]
                    quad = curve_to_quadratic(cubic, self.max_err)
                    if self.stats is not None:
                        n = str(len(quad) - 2)
                        self.stats[n] = self.stats.get(n, 0) + 1
                    new_points = [(pt, False, None, {}) for pt in quad[1:-1]]
                    new_points.append((on_curve, smooth, name, kwargs))
                    new_segments.append(["qcurve", new_points])
                    prev_on_curve = sub_points[-1][0]
            else:
                new_segments.append([segment_type, points])
                prev_on_curve = points[-1][0]
        return new_segments


class Qu2CuPointPen(BaseFilterPointPen):
    """ A filter pen to convert quadratic b-splines curves to cubic bezier
    curves using the RoboFab PointPen protocol.

    other_point_pen: another PointPen used to draw the transformed outline.
    reverse_direction: reverse the winding direction of all contours.
    """

    def _filter_segments(self, segments):
        new_segments = []
        prev_points = segments[-1][1]
        prev_on_curve = prev_points[-1][0]
        for segment_type, points in segments:
            if segment_type == 'qcurve':
                on_curve, smooth, name, kwargs = points[-1]
                quadratic = [prev_on_curve] + [p[0] for p in points[:-1]] + [on_curve]
                curve = quadratic_to_curve(quadratic)
                new_points = [(pt, False, None, {}) for pt in curve[1:-1]]
                new_points.append((on_curve, smooth, name, kwargs))
                new_segments.append(["curve", new_points])
                prev_on_curve = on_curve
            else:
                new_segments.append([segment_type, points])
                prev_on_curve = points[-1][0]
        return new_segments
