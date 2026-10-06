function solve(square) {
  return ((1n << BigInt(square)) - 1n).toString();
}
