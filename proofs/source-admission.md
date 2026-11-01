# Result-only admission for the frozen Python carriers

The receiver selects one of the twelve trusted task definitions. The candidate
must parse and compile as exactly that ordinary function, with an additional
prefix of at most 24 statements. After deleting the prefix, its complete
module AST, including signature and every functional statement, must equal the
receiver reference AST. A marker is an actual immediately preceding comment
token; a string or a different site identifier cannot supply it.

The only admitted prefix statements are a fresh local integer-zero assignment,
an `if False` with a sole `pass`, or an empty-tuple `for` with a sole `pass` and
no else. The assignment/loop name is absent from every reference name and
argument, has the declared indexed spelling, and is not reused. Site indices
are distinct and increasing. The integer-zero check excludes Boolean constants.

## Erasure lemma

Under ordinary Python result-only execution of the trusted task on its declared
builtin-input domain, without frame/reflection observation or resource-failure
observations, an admitted candidate has the reference result and termination
behavior. No candidate program needs to execute to establish this relation.

Proof: a zero assignment terminates and changes only a fresh, unread local. Its
compile-time local binding cannot shadow a reference name. A false branch has
no executed body, and an empty tuple loop has no iterations; its target is also
fresh. Erasing the prefix therefore preserves the reference state on every
name it can observe. Induction over prefix length reaches the identical
remaining function body, whose execution starts with the same observable
state. The module/signature equality excludes altered defaults, decorators,
top-level effects and changed functional code. The same argument covers the
empty prefix and deletion of any subset of carrier sites.

The registry's lack of introspection and external frame observations is a
premise, not something proved for arbitrary Python by a name denylist. It was
checked for these twelve frozen references. The result does not promise equal
timing, memory, local-variable dictionaries, tracing events, code objects, or
arbitrary contextual equivalence. It does not apply to JavaScript or to external
watermark implementations.

## Decision linkage and fair comparison

Only after admission does the consumer read actual indexed syntax and use it
in the existing detector. Each rendered source is identified separately from
its indexed model; disagreement stops analysis. Exact repeated source bytes
under the same receiver task may reuse their AST admission, not an unrelated
semantic label. This gives source-bound proof-derived admission rather than
new executed validity labels. Historical 432 executed dense links and their
75,600 missing labels remain historical.

The original marker regex is only an extraction control, not an equally strong
semantic baseline. Inserting division by zero into a carrier assignment can
leave its extracted bits unchanged. The new gate rejects the statement. A
direct receiver applying the same AST-erasure contract has the same information
and can make the same decision without a certificate; no detection-accuracy,
runtime or information advantage over that receiver is claimed.
