function solve(x, y) {

  const radius2 = x * x + y * y;
  if (radius2 <= 1) return 10;
  if (radius2 <= 25) return 5;
  if (radius2 <= 100) return 1;
  return 0;
}
