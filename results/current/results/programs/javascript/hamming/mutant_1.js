function solve(left, right) {
  if (left.length !== right.length) return {error: "length"};
  let distance = 0;
  for (let i = 0; i < left.length; i += 1) if (left[i] === right[i]) distance += 1;
  return distance;
}
