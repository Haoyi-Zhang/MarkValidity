
"use strict";

const fs = require("fs");
const crypto = require("crypto");

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    const output = {};
    for (const key of Object.keys(value).sort()) output[key] = canonicalize(value[key]);
    return output;
  }
  return value;
}

function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

function compileProgram(source) {
  return new Function(`${source}\nreturn solve;`)();
}

function evaluate(fn, cases) {
  const outputs = [];
  const hash = crypto.createHash("sha256");
  for (const args of cases) {
    let value;
    try {
      value = fn(...args);
    } catch (error) {
      value = {exception: error.name, message: String(error.message || error)};
    }
    outputs.push(value);
    hash.update(canonicalJson(value), "utf8");
    hash.update("\n", "utf8");
  }
  return {outputs, digest: hash.digest("hex")};
}

function firstMismatch(reference, candidate) {
  const length = Math.min(reference.length, candidate.length);
  for (let i = 0; i < length; i += 1) {
    if (canonicalJson(reference[i]) !== canonicalJson(candidate[i])) return i;
  }
  return reference.length === candidate.length ? null : length;
}

function main() {
  if (process.argv.length !== 3) {
    throw new Error("usage: node batch_runner.js SPEC.json");
  }
  const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const result = {node_version: process.version, tasks: {}};

  for (const [taskName, task] of Object.entries(spec.tasks)) {
    const taskResult = {programs: []};
    let referenceDomain = null;
    let referenceNominal = null;

    for (const program of task.programs) {
      try {
        const fn = compileProgram(program.source);
        const domain = evaluate(fn, task.cases);
        const nominal = evaluate(fn, task.nominal_cases);
        if (program.role === "reference") {
          referenceDomain = domain.outputs;
          referenceNominal = nominal.outputs;
        }
        if (referenceDomain === null || referenceNominal === null) {
          throw new Error("reference must be the first program");
        }
        taskResult.programs.push({
          id: program.id,
          role: program.role,
          parse_ok: true,
          domain_hash: domain.digest,
          nominal_hash: nominal.digest,
          domain_equal: firstMismatch(referenceDomain, domain.outputs) === null,
          nominal_equal: firstMismatch(referenceNominal, nominal.outputs) === null,
          first_mismatch_index: firstMismatch(referenceDomain, domain.outputs),
          error: "",
        });
      } catch (error) {
        taskResult.programs.push({
          id: program.id,
          role: program.role,
          parse_ok: false,
          domain_hash: "",
          nominal_hash: "",
          domain_equal: false,
          nominal_equal: false,
          first_mismatch_index: null,
          error: String(error.stack || error),
        });
      }
    }
    result.tasks[taskName] = taskResult;
  }
  process.stdout.write(JSON.stringify(result));
}

main();
