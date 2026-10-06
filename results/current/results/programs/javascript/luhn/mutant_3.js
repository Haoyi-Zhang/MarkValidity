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
