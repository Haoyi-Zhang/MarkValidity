function solve(text) {
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c));
  return new Set(letters).size >= letters.length - 1;
}
