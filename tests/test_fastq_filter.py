# Copyright (c) 2021 Leiden University Medical Center
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import array
import itertools
import math
import statistics
import sys
from typing import List

from dnaio import Sequence

import fastq_filter
from fastq_filter import fallback_algorithms, max_length_filter, \
    mean_quality_filter, median_quality_filter, min_length_filter, \
    optimized_algorithms
from fastq_filter.constants import DEFAULT_PHRED_SCORE_OFFSET

import pytest  # type: ignore


def quallist_to_string(quallist: List[int]):
    return array.array(
        "B", [qual + DEFAULT_PHRED_SCORE_OFFSET for qual in quallist]
    ).tobytes().decode("ascii")


QUAL_STRINGS = [
    b"I?>DC:>@?IDC9??G?>EH9E@66=9<?@E?DC:@<@BBFG>=FIC@F9>7CG?IC?I;CD9>>>A@C7>>"
    b"8>>D9GCB<;?DD>C;9?>5G>?H?=6@>:G6B<?==A7?@???8IF<75C=@A:BEA@A;C89D:=1?=<A"
    b">D=>B66C",
    b"C:@?;8@=DC???>E>E;98BBB?9D=?@B;D?I:??FD8CH?A7?<H>ABD@C@C?>;;B<><;9@8BAFD"
    b"?;:>I3DB<?<B=?A??CI>2E>><BD?A??FCBCE?DAI><B:8D>?C>@BA=F<>7=E=?DC=@9GG=>?"
    b"C@><CA;>",
]


@pytest.mark.parametrize(
    ["function", "qualstring"],
    itertools.product(
        [optimized_algorithms.qualmean, fallback_algorithms.qualmean],
        QUAL_STRINGS)
)
def test_qualmean(qualstring, function):
    offset = DEFAULT_PHRED_SCORE_OFFSET
    qualities = [qual - offset for qual in array.array("b", qualstring)]
    probabilities = [10 ** (qual / -10) for qual in qualities]
    average_prob = statistics.mean(probabilities)
    phred = - 10 * math.log10(average_prob)
    assert phred == pytest.approx(function(qualstring))


@pytest.mark.parametrize(
    ["function", "qualstring"], itertools.product(
        [optimized_algorithms.qualmedian, fallback_algorithms.qualmedian],
        QUAL_STRINGS)
)
def test_qualmedian(qualstring, function):
    offset = DEFAULT_PHRED_SCORE_OFFSET
    qualities = [qual - offset for qual in array.array("b", qualstring)]
    median_quality = statistics.median(qualities)
    assert median_quality == function(qualstring)


def test_min_length_filter_pass():
    assert min_length_filter(
        10, Sequence("", "0123456789A", "???????????")) is True


def test_min_length_filter_fail():
    assert min_length_filter(
        12, Sequence("", "0123456789A", "???????????")) is False


def test_max_length_filter_pass():
    assert max_length_filter(
        12, Sequence("", "0123456789A", "???????????")) is True


def test_max_length_filter_fail():
    assert max_length_filter(
        10, Sequence("", "0123456789A", "???????????")) is False


def test_mean_quality_filter_fail():
    assert mean_quality_filter(
        10, Sequence("", "AAA", quallist_to_string([9, 9, 9]))) is False


def test_mean_quality_filter_pass():
    assert mean_quality_filter(
        8, Sequence("", "AAA", quallist_to_string([9, 9, 9]))) is True


def test_median_quality_filter_fail():
    assert median_quality_filter(
        10, Sequence("", "AAAAA", quallist_to_string([9, 9, 9, 10, 10]))
    ) is False


def test_median_quality_filter_pass():
    assert median_quality_filter(
        8-0.001, Sequence(
            "", "AAAAAAA", quallist_to_string([1, 1, 1, 8, 9, 9, 9]))) is True


def test_fastq_records_to_file(tmp_path):
    records = [Sequence("TEST", "A", "A")] * 3
    out = tmp_path / "test.fq"
    fastq_filter.fastq_records_to_file(records, str(out))
    assert out.read_bytes() == b"@TEST\nA\n+\nA\n" \
                               b"@TEST\nA\n+\nA\n" \
                               b"@TEST\nA\n+\nA\n"


def test_file_to_fastq_records(tmp_path):
    out = tmp_path / "test.fq"
    out.write_bytes(b"@TEST\nA\n+\nA\n@TEST\nA\n+\nA\n@TEST\nA\n+\nA\n")
    assert list(fastq_filter.file_to_fastq_records(str(out))) == [
        Sequence("TEST", "A", "A")] * 3


def test_filter_fastq(tmp_path):
    in_f = tmp_path / "in.fq"
    out_f = tmp_path / "out.fq"
    in_f.write_bytes(b"@TEST\nAA\n+\nAA\n@TEST\nA\n+\n-\n@TEST\nA\n+\nA\n")
    fastq_filter.filter_fastq(
        "mean_quality:20|min_length:2", str(in_f), str(out_f))
    # Only one record should survive the filter.
    assert out_f.read_bytes() == b"@TEST\nAA\n+\nAA\n"


def test_main(tmp_path):
    in_f = tmp_path / "in.fq"
    out_f = tmp_path / "out.fq"
    in_f.write_bytes(b"@TEST\nAA\n+\nAA\n@TEST\nA\n+\n-\n@TEST\nA\n+\nA\n")
    sys.argv = ["", "-o", str(out_f), "mean_quality:20|min_length:2",
                str(in_f)]
    fastq_filter.main()
    assert out_f.read_bytes() == b"@TEST\nAA\n+\nAA\n"
