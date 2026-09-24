function solve(n) {
  const digits = [...String(n)].map(Number);
  const power = digits.length + 1;
  return digits.reduce((sum, d) => sum + d ** power, 0) === n;
}
