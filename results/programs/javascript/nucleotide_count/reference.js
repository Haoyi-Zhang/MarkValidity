function solve(text) {

  const out = {A: 0, C: 0, G: 0, T: 0};
  for (const c of text) out[c] += 1;
  return out;
}
