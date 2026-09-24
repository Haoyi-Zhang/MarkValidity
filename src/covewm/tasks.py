
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class TaskSpec:
    name: str
    domain_size: int
    nominal_cases: tuple[tuple, ...]
    python_reference: str
    python_mutants: tuple[str, ...]
    javascript_reference: str
    javascript_mutants: tuple[str, ...]
    mutant_descriptions: tuple[str, ...]
    construct_note: str


def _strings(alphabet: str, max_len: int) -> list[str]:
    values: list[str] = []
    for length in range(max_len + 1):
        values.extend("".join(chars) for chars in product(alphabet, repeat=length))
    return values


def domain_cases(name: str) -> list[list]:
    """Return the frozen finite domain as JSON-compatible argument lists."""
    if name == "leap_year":
        cases = [[year] for year in range(1200, 2001)]
    elif name == "collatz_steps":
        cases = [[n] for n in range(1, 501)]
    elif name == "raindrops":
        cases = [[n] for n in range(1, 501)]
    elif name == "grains":
        cases = [[square] for square in range(1, 65)]
    elif name == "hamming":
        base = _strings("AC", 5) + ["G", "T", "AG"]
        cases = [[left, right] for left in base for right in base]
        cases.extend([["GT", base[i]] for i in range(13)])
    elif name == "isogram":
        cases = [[text] for text in _strings("abcd", 5)]
    elif name == "triangle":
        cases = [[a, b, c] for a in range(11) for b in range(11) for c in range(11)]
    elif name == "luhn":
        cases = [[f"{n:05d}"] for n in range(11000)]
    elif name == "darts":
        cases = [[x, y] for x in range(-12, 13) for y in range(-12, 13)]
    elif name == "armstrong":
        cases = [[n] for n in range(10000)]
    elif name == "nucleotide_count":
        cases = [[text] for text in _strings("ACGT", 5)]
    elif name == "reverse_text":
        cases = [[text] for text in _strings("abc", 6)]
    else:
        raise KeyError(name)
    return cases


TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        name="leap_year",
        domain_size=801,
        nominal_cases=((1996,), (1900,), (1999,), (1992,), (1800,)),
        python_reference="""\
def solve(year):
__CARRIERS__
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
""",
        python_mutants=(
"""\
def solve(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 800 == 0)
""",
"""\
def solve(year):
    return year % 4 == 0
""",
"""\
def solve(year):
    return year % 4 == 0 and year % 100 != 0 and year % 400 == 0
""",
        ),
        javascript_reference="""\
function solve(year) {
__CARRIERS__
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}
""",
        javascript_mutants=(
"""\
function solve(year) {
  return year % 4 === 0 && (year % 100 !== 0 || year % 800 === 0);
}
""",
"""\
function solve(year) {
  return year % 4 === 0;
}
""",
"""\
function solve(year) {
  return year % 4 === 0 && year % 100 !== 0 && year % 400 === 0;
}
""",
        ),
        mutant_descriptions=(
            "Narrow the 400-year exception to 800 years.",
            "Ignore century exceptions.",
            "Require mutually incompatible century conditions.",
        ),
        construct_note="Sparse calendar boundaries, including century and 400-year exceptions.",
    ),
    TaskSpec(
        name="collatz_steps",
        domain_size=500,
        nominal_cases=((1,), (3,), (12,), (16,), (27,)),
        python_reference="""\
def solve(n):
__CARRIERS__
    steps = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
        if steps > 10000:
            return {"error": "guard"}
    return steps
""",
        python_mutants=(
"""\
def solve(n):
    steps = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n - 1
        steps += 1
        if steps > 10000:
            return {"error": "guard"}
    return steps
""",
"""\
def solve(n):
    steps = 0
    while n != 1:
        n = n // 4 if n % 4 == 0 else (n // 2 if n % 2 == 0 else 3 * n + 1)
        steps += 1
        if steps > 10000:
            return {"error": "guard"}
    return steps
""",
"""\
def solve(n):
    steps = 1
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
        if steps > 10000:
            return {"error": "guard"}
    return steps
""",
        ),
        javascript_reference="""\
function solve(n) {
__CARRIERS__
  let steps = 0;
  while (n !== 1) {
    n = n % 2 === 0 ? Math.floor(n / 2) : 3 * n + 1;
    steps += 1;
    if (steps > 10000) return {error: "guard"};
  }
  return steps;
}
""",
        javascript_mutants=(
"""\
function solve(n) {
  let steps = 0;
  while (n !== 1) {
    n = n % 2 === 0 ? Math.floor(n / 2) : 3 * n - 1;
    steps += 1;
    if (steps > 10000) return {error: "guard"};
  }
  return steps;
}
""",
"""\
function solve(n) {
  let steps = 0;
  while (n !== 1) {
    n = n % 4 === 0 ? Math.floor(n / 4) : (n % 2 === 0 ? Math.floor(n / 2) : 3 * n + 1);
    steps += 1;
    if (steps > 10000) return {error: "guard"};
  }
  return steps;
}
""",
"""\
function solve(n) {
  let steps = 1;
  while (n !== 1) {
    n = n % 2 === 0 ? Math.floor(n / 2) : 3 * n + 1;
    steps += 1;
    if (steps > 10000) return {error: "guard"};
  }
  return steps;
}
""",
        ),
        mutant_descriptions=(
            "Change the odd recurrence from 3n+1 to 3n-1.",
            "Divide multiples of four by four in one step.",
            "Initialize the step counter to one.",
        ),
        construct_note="Iterative control flow with a termination guard.",
    ),
    TaskSpec(
        name="raindrops",
        domain_size=500,
        nominal_cases=((1,), (3,), (5,), (7,), (105,)),
        python_reference="""\
def solve(n):
__CARRIERS__
    text = ""
    if n % 3 == 0:
        text += "Pling"
    if n % 5 == 0:
        text += "Plang"
    if n % 7 == 0:
        text += "Plong"
    return text or str(n)
""",
        python_mutants=(
"""\
def solve(n):
    text = ""
    if n % 2 == 0:
        text += "Pling"
    if n % 5 == 0:
        text += "Plang"
    if n % 7 == 0:
        text += "Plong"
    return text or str(n)
""",
"""\
def solve(n):
    if n % 3 == 0:
        return "Pling"
    elif n % 5 == 0:
        return "Plang"
    elif n % 7 == 0:
        return "Plong"
    return str(n)
""",
"""\
def solve(n):
    text = ""
    if n % 3 == 0:
        text += "Pling"
    if n % 5 == 0:
        text += "Plang"
    return text or str(n)
""",
        ),
        javascript_reference="""\
function solve(n) {
__CARRIERS__
  let text = "";
  if (n % 3 === 0) text += "Pling";
  if (n % 5 === 0) text += "Plang";
  if (n % 7 === 0) text += "Plong";
  return text || String(n);
}
""",
        javascript_mutants=(
"""\
function solve(n) {
  let text = "";
  if (n % 2 === 0) text += "Pling";
  if (n % 5 === 0) text += "Plang";
  if (n % 7 === 0) text += "Plong";
  return text || String(n);
}
""",
"""\
function solve(n) {
  if (n % 3 === 0) return "Pling";
  else if (n % 5 === 0) return "Plang";
  else if (n % 7 === 0) return "Plong";
  return String(n);
}
""",
"""\
function solve(n) {
  let text = "";
  if (n % 3 === 0) text += "Pling";
  if (n % 5 === 0) text += "Plang";
  return text || String(n);
}
""",
        ),
        mutant_descriptions=(
            "Change the first factor from three to two.",
            "Make factor branches mutually exclusive.",
            "Omit the factor-seven channel.",
        ),
        construct_note="Independent branch composition.",
    ),
    TaskSpec(
        name="grains",
        domain_size=64,
        nominal_cases=((1,), (2,), (3,), (16,), (64,)),
        python_reference="""\
def solve(square):
__CARRIERS__
    return str(1 << (square - 1))
""",
        python_mutants=(
"""\
def solve(square):
    return str(1 << square)
""",
"""\
def solve(square):
    return str(3 ** (square - 1))
""",
"""\
def solve(square):
    return str((1 << square) - 1)
""",
        ),
        javascript_reference="""\
function solve(square) {
__CARRIERS__
  return (1n << BigInt(square - 1)).toString();
}
""",
        javascript_mutants=(
"""\
function solve(square) {
  return (1n << BigInt(square)).toString();
}
""",
"""\
function solve(square) {
  return (3n ** BigInt(square - 1)).toString();
}
""",
"""\
function solve(square) {
  return ((1n << BigInt(square)) - 1n).toString();
}
""",
        ),
        mutant_descriptions=(
            "Shift the exponent by one.",
            "Use base three.",
            "Return the cumulative total through the square.",
        ),
        construct_note="Exact exponential arithmetic represented as decimal text.",
    ),
    TaskSpec(
        name="hamming",
        domain_size=4369,
        nominal_cases=(("", ""), ("A", "A"), ("A", "G"), ("GATT", "GACT"), ("A", "")),
        python_reference="""\
def solve(left, right):
__CARRIERS__
    if len(left) != len(right):
        return {"error": "length"}
    return sum(a != b for a, b in zip(left, right))
""",
        python_mutants=(
"""\
def solve(left, right):
    if len(left) != len(right):
        return {"error": "length"}
    return sum(a == b for a, b in zip(left, right))
""",
"""\
def solve(left, right):
    return sum(a != b for a, b in zip(left, right))
""",
"""\
def solve(left, right):
    if len(left) != len(right):
        return {"error": "length"}
    return 1 + sum(a != b for a, b in zip(left, right))
""",
        ),
        javascript_reference="""\
function solve(left, right) {
__CARRIERS__
  if (left.length !== right.length) return {error: "length"};
  let distance = 0;
  for (let i = 0; i < left.length; i += 1) if (left[i] !== right[i]) distance += 1;
  return distance;
}
""",
        javascript_mutants=(
"""\
function solve(left, right) {
  if (left.length !== right.length) return {error: "length"};
  let distance = 0;
  for (let i = 0; i < left.length; i += 1) if (left[i] === right[i]) distance += 1;
  return distance;
}
""",
"""\
function solve(left, right) {
  let distance = 0;
  const n = Math.min(left.length, right.length);
  for (let i = 0; i < n; i += 1) if (left[i] !== right[i]) distance += 1;
  return distance;
}
""",
"""\
function solve(left, right) {
  if (left.length !== right.length) return {error: "length"};
  let distance = 1;
  for (let i = 0; i < left.length; i += 1) if (left[i] !== right[i]) distance += 1;
  return distance;
}
""",
        ),
        mutant_descriptions=(
            "Count equal positions instead of unequal positions.",
            "Ignore unequal-length preconditions.",
            "Add one to every distance.",
        ),
        construct_note="Pairwise sequence comparison and length precondition.",
    ),
    TaskSpec(
        name="isogram",
        domain_size=1365,
        nominal_cases=(("",), ("abc",), ("aba",), ("abca",), ("letter",)),
        python_reference="""\
def solve(text):
__CARRIERS__
    letters = [c.lower() for c in text if c.isalpha()]
    return len(letters) == len(set(letters))
""",
        python_mutants=(
"""\
def solve(text):
    letters = [c.lower() for c in text if c.isalpha()]
    return all(letters[i] != letters[i - 1] for i in range(1, len(letters)))
""",
"""\
def solve(text):
    letters = [c.lower() for c in text if c.isalpha()]
    return len(set(letters)) >= len(letters) - 1
""",
"""\
def solve(text):
    letters = [c.lower() for c in text if c.isalpha()]
    return len(letters[:-1]) == len(set(letters[:-1]))
""",
        ),
        javascript_reference="""\
function solve(text) {
__CARRIERS__
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c));
  return new Set(letters).size === letters.length;
}
""",
        javascript_mutants=(
"""\
function solve(text) {
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c));
  for (let i = 1; i < letters.length; i += 1) if (letters[i] === letters[i - 1]) return false;
  return true;
}
""",
"""\
function solve(text) {
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c));
  return new Set(letters).size >= letters.length - 1;
}
""",
"""\
function solve(text) {
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c)).slice(0, -1);
  return new Set(letters).size === letters.length;
}
""",
        ),
        mutant_descriptions=(
            "Check only adjacent duplicates.",
            "Allow one repeated letter.",
            "Drop the final letter before checking.",
        ),
        construct_note="Set-based lexical predicate.",
    ),
    TaskSpec(
        name="triangle",
        domain_size=1331,
        nominal_cases=((1, 1, 2), (2, 2, 2), (2, 2, 3), (2, 3, 3), (2, 3, 4)),
        python_reference="""\
def solve(a, b, c):
__CARRIERS__
    if min(a, b, c) <= 0 or a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b or a == c or b == c:
        return "isosceles"
    return "scalene"
""",
        python_mutants=(
"""\
def solve(a, b, c):
    if min(a, b, c) <= 0 or a + b < c or a + c < b or b + c < a:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b or a == c or b == c:
        return "isosceles"
    return "scalene"
""",
"""\
def solve(a, b, c):
    if min(a, b, c) <= 0 or a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b:
        return "isosceles"
    return "scalene"
""",
"""\
def solve(a, b, c):
    if min(a, b, c) <= 0 or a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b:
        return "equilateral"
    if a == b or a == c or b == c:
        return "isosceles"
    return "scalene"
""",
        ),
        javascript_reference="""\
function solve(a, b, c) {
__CARRIERS__
  if (Math.min(a, b, c) <= 0 || a + b <= c || a + c <= b || b + c <= a) return "invalid";
  if (a === b && b === c) return "equilateral";
  if (a === b || a === c || b === c) return "isosceles";
  return "scalene";
}
""",
        javascript_mutants=(
"""\
function solve(a, b, c) {
  if (Math.min(a, b, c) <= 0 || a + b < c || a + c < b || b + c < a) return "invalid";
  if (a === b && b === c) return "equilateral";
  if (a === b || a === c || b === c) return "isosceles";
  return "scalene";
}
""",
"""\
function solve(a, b, c) {
  if (Math.min(a, b, c) <= 0 || a + b <= c || a + c <= b || b + c <= a) return "invalid";
  if (a === b && b === c) return "equilateral";
  if (a === b) return "isosceles";
  return "scalene";
}
""",
"""\
function solve(a, b, c) {
  if (Math.min(a, b, c) <= 0 || a + b <= c || a + c <= b || b + c <= a) return "invalid";
  if (a === b) return "equilateral";
  if (a === b || a === c || b === c) return "isosceles";
  return "scalene";
}
""",
        ),
        mutant_descriptions=(
            "Accept degenerate triangles by using strict inequalities.",
            "Recognize only one isosceles orientation.",
            "Misclassify any a=b triangle as equilateral.",
        ),
        construct_note="Piecewise geometric classification and equality boundaries.",
    ),
    TaskSpec(
        name="luhn",
        domain_size=11000,
        nominal_cases=(("00000",), ("00018",), ("05900",), ("05545",), ("79927",)),
        python_reference="""\
def solve(text):
__CARRIERS__
    digits = [int(c) for c in text if c.isdigit()]
    if len(digits) <= 1:
        return False
    total = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        value = digit
        if i % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
""",
        python_mutants=(
"""\
def solve(text):
    digits = [int(c) for c in text if c.isdigit()]
    if len(digits) <= 1:
        return False
    total = 0
    parity = (len(digits) + 1) % 2
    for i, digit in enumerate(digits):
        value = digit
        if i % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
""",
"""\
def solve(text):
    digits = [int(c) for c in text if c.isdigit()]
    total = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        value = digit * 2 if i % 2 == parity else digit
        total += value
    return len(digits) > 1 and total % 10 == 0
""",
"""\
def solve(text):
    digits = [int(c) for c in text if c.isdigit()]
    if len(digits) <= 1:
        return False
    total = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        value = digit
        if i % 2 == parity:
            value *= 2
            if value > 9:
                value -= 8
        total += value
    return total % 10 == 0
""",
        ),
        javascript_reference="""\
function solve(text) {
__CARRIERS__
  const digits = [...text].filter(c => /[0-9]/.test(c)).map(Number);
  if (digits.length <= 1) return false;
  let total = 0;
  const parity = digits.length % 2;
  for (let i = 0; i < digits.length; i += 1) {
    let value = digits[i];
    if (i % 2 === parity) {
      value *= 2;
      if (value > 9) value -= 9;
    }
    total += value;
  }
  return total % 10 === 0;
}
""",
        javascript_mutants=(
"""\
function solve(text) {
  const digits = [...text].filter(c => /[0-9]/.test(c)).map(Number);
  if (digits.length <= 1) return false;
  let total = 0;
  const parity = (digits.length + 1) % 2;
  for (let i = 0; i < digits.length; i += 1) {
    let value = digits[i];
    if (i % 2 === parity) {
      value *= 2;
      if (value > 9) value -= 9;
    }
    total += value;
  }
  return total % 10 === 0;
}
""",
"""\
function solve(text) {
  const digits = [...text].filter(c => /[0-9]/.test(c)).map(Number);
  let total = 0;
  const parity = digits.length % 2;
  for (let i = 0; i < digits.length; i += 1) total += i % 2 === parity ? digits[i] * 2 : digits[i];
  return digits.length > 1 && total % 10 === 0;
}
""",
"""\
function solve(text) {
  const digits = [...text].filter(c => /[0-9]/.test(c)).map(Number);
  if (digits.length <= 1) return false;
  let total = 0;
  const parity = digits.length % 2;
  for (let i = 0; i < digits.length; i += 1) {
    let value = digits[i];
    if (i % 2 === parity) {
      value *= 2;
      if (value > 9) value -= 8;
    }
    total += value;
  }
  return total % 10 === 0;
}
""",
        ),
        mutant_descriptions=(
            "Reverse the doubling parity.",
            "Omit the subtract-nine correction.",
            "Subtract eight rather than nine after doubling.",
        ),
        construct_note="Parity-sensitive checksum iteration and leading zeros.",
    ),
    TaskSpec(
        name="darts",
        domain_size=625,
        nominal_cases=((0, 0), (2, 0), (3, 4), (7, 0), (11, 0)),
        python_reference="""\
def solve(x, y):
__CARRIERS__
    radius2 = x * x + y * y
    if radius2 <= 1:
        return 10
    if radius2 <= 25:
        return 5
    if radius2 <= 100:
        return 1
    return 0
""",
        python_mutants=(
"""\
def solve(x, y):
    radius2 = x * x + y * y
    if radius2 <= 1:
        return 10
    if radius2 <= 25:
        return 5
    if radius2 <= 90:
        return 1
    return 0
""",
"""\
def solve(x, y):
    radius2 = x * x + y * y
    if radius2 <= 4:
        return 10
    if radius2 <= 25:
        return 5
    if radius2 <= 100:
        return 1
    return 0
""",
"""\
def solve(x, y):
    radius2 = x * x + y * y
    if radius2 <= 1:
        return 10
    if radius2 < 25:
        return 5
    if radius2 <= 100:
        return 1
    return 0
""",
        ),
        javascript_reference="""\
function solve(x, y) {
__CARRIERS__
  const radius2 = x * x + y * y;
  if (radius2 <= 1) return 10;
  if (radius2 <= 25) return 5;
  if (radius2 <= 100) return 1;
  return 0;
}
""",
        javascript_mutants=(
"""\
function solve(x, y) {
  const radius2 = x * x + y * y;
  if (radius2 <= 1) return 10;
  if (radius2 <= 25) return 5;
  if (radius2 <= 90) return 1;
  return 0;
}
""",
"""\
function solve(x, y) {
  const radius2 = x * x + y * y;
  if (radius2 <= 4) return 10;
  if (radius2 <= 25) return 5;
  if (radius2 <= 100) return 1;
  return 0;
}
""",
"""\
function solve(x, y) {
  const radius2 = x * x + y * y;
  if (radius2 <= 1) return 10;
  if (radius2 < 25) return 5;
  if (radius2 <= 100) return 1;
  return 0;
}
""",
        ),
        mutant_descriptions=(
            "Shift the outer squared-radius threshold from 100 to 90.",
            "Expand the inner ring from radius one to radius two.",
            "Make the middle boundary strict.",
        ),
        construct_note="Piecewise geometric thresholds.",
    ),
    TaskSpec(
        name="armstrong",
        domain_size=10000,
        nominal_cases=((0,), (1,), (153,), (9474,), (10,), (9475,)),
        python_reference="""\
def solve(n):
__CARRIERS__
    digits = [int(c) for c in str(n)]
    power = len(digits)
    return sum(d ** power for d in digits) == n
""",
        python_mutants=(
"""\
def solve(n):
    digits = [int(c) for c in str(n)]
    return sum(d ** 3 for d in digits) == n
""",
"""\
def solve(n):
    digits = [int(c) for c in str(n)]
    power = len(digits)
    return sum(d ** power for d in digits) == n or n == 10
""",
"""\
def solve(n):
    digits = [int(c) for c in str(n)]
    power = len(digits) + 1
    return sum(d ** power for d in digits) == n
""",
        ),
        javascript_reference="""\
function solve(n) {
__CARRIERS__
  const digits = [...String(n)].map(Number);
  const power = digits.length;
  return digits.reduce((sum, d) => sum + d ** power, 0) === n;
}
""",
        javascript_mutants=(
"""\
function solve(n) {
  const digits = [...String(n)].map(Number);
  return digits.reduce((sum, d) => sum + d ** 3, 0) === n;
}
""",
"""\
function solve(n) {
  const digits = [...String(n)].map(Number);
  const power = digits.length;
  return digits.reduce((sum, d) => sum + d ** power, 0) === n || n === 10;
}
""",
"""\
function solve(n) {
  const digits = [...String(n)].map(Number);
  const power = digits.length + 1;
  return digits.reduce((sum, d) => sum + d ** power, 0) === n;
}
""",
        ),
        mutant_descriptions=(
            "Use a fixed cubic exponent.",
            "Add an erroneous special case for ten.",
            "Increase the digit-count exponent by one.",
        ),
        construct_note="Digit aggregation with a length-dependent exponent.",
    ),
    TaskSpec(
        name="nucleotide_count",
        domain_size=1365,
        nominal_cases=(("",), ("A",), ("CG",), ("ACGT",), ("CCGG",)),
        python_reference="""\
def solve(text):
__CARRIERS__
    return {base: text.count(base) for base in "ACGT"}
""",
        python_mutants=(
"""\
def solve(text):
    return {"A": text.count("A"), "C": text.count("G"), "G": text.count("C"), "T": text.count("T")}
""",
"""\
def solve(text):
    return {"A": text.count("A"), "C": text.count("C"), "G": text.count("G"), "T": 0}
""",
"""\
def solve(text):
    return {"A": 0, "C": text.count("C") + text.count("A"), "G": text.count("G"), "T": text.count("T")}
""",
        ),
        javascript_reference="""\
function solve(text) {
__CARRIERS__
  const out = {A: 0, C: 0, G: 0, T: 0};
  for (const c of text) out[c] += 1;
  return out;
}
""",
        javascript_mutants=(
"""\
function solve(text) {
  const out = {A: 0, C: 0, G: 0, T: 0};
  for (const c of text) out[c] += 1;
  return {A: out.A, C: out.G, G: out.C, T: out.T};
}
""",
"""\
function solve(text) {
  const out = {A: 0, C: 0, G: 0, T: 0};
  for (const c of text) if (c !== "T") out[c] += 1;
  return out;
}
""",
"""\
function solve(text) {
  const out = {A: 0, C: 0, G: 0, T: 0};
  for (const c of text) {
    if (c === "A") out.C += 1;
    else out[c] += 1;
  }
  return out;
}
""",
        ),
        mutant_descriptions=(
            "Swap the C and G output channels.",
            "Omit T counts.",
            "Accumulate A symbols in the C channel.",
        ),
        construct_note="Structured map output and per-symbol counting.",
    ),
    TaskSpec(
        name="reverse_text",
        domain_size=1093,
        nominal_cases=(("",), ("a",), ("abc",), ("abba",), ("abcabc",)),
        python_reference="""\
def solve(text):
__CARRIERS__
    return text[::-1]
""",
        python_mutants=(
"""\
def solve(text):
    return text
""",
"""\
def solve(text):
    return text[-2::-1] if text else text
""",
"""\
def solve(text):
    return "".join(sorted(text, reverse=True))
""",
        ),
        javascript_reference="""\
function solve(text) {
__CARRIERS__
  return [...text].reverse().join("");
}
""",
        javascript_mutants=(
"""\
function solve(text) {
  return text;
}
""",
"""\
function solve(text) {
  return [...text].slice(0, -1).reverse().join("");
}
""",
"""\
function solve(text) {
  return [...text].sort().reverse().join("");
}
""",
        ),
        mutant_descriptions=(
            "Return the input unchanged.",
            "Drop the final character before reversing.",
            "Sort characters instead of reversing their order.",
        ),
        construct_note="Order-sensitive sequence transformation.",
    ),
)


TASK_BY_NAME = {task.name: task for task in TASKS}


def validate_domains() -> None:
    total = 0
    for task in TASKS:
        cases = domain_cases(task.name)
        if len(cases) != task.domain_size:
            raise AssertionError(f"{task.name}: {len(cases)} != {task.domain_size}")
        total += len(cases)
    if total != 33013:
        raise AssertionError(total)
