function solve(a, b, c) {
  if (Math.min(a, b, c) <= 0 || a + b < c || a + c < b || b + c < a) return "invalid";
  if (a === b && b === c) return "equilateral";
  if (a === b || a === c || b === c) return "isosceles";
  return "scalene";
}
