function solve(left, right) {
  let distance = 0;
  const n = Math.min(left.length, right.length);
  for (let i = 0; i < n; i += 1) if (left[i] !== right[i]) distance += 1;
  return distance;
}
