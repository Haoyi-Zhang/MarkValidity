function solve(text) {
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c)).slice(0, -1);
  return new Set(letters).size === letters.length;
}
