# UI acceptance transition

The [requirement register](product-requirements.md) and the
[migration manifest](migration-manifest.json) record product acceptance, but
their checkpoint, revision, archive and inventory audits never grant it. This
transition (roadmap UI-11) is the one audit that may mark a requirement
verified, accept a milestone or final gate, or accept a migration resource.
Those audits keep their restrictions.

`tools/ui/validate_product_requirements.py --acceptance` runs it; the rules live
in `tools/ui/acceptance_transition.py` so that they can be reviewed apart from
the other modes. No requirement or resource has been accepted with it yet.

## What a transition names

A transition lists every requirement it accepts with `--accept ID` and every
migration resource with `--accept-resource RESOURCE_ID` (the manifest's
`path@closure` identity). Nothing else in the register or manifest may change.
There is no flag that accepts a group, a milestone or the corpus, and the audit
fails if a record claims a requirement or resource the transition does not name.

Each accepted requirement moves from pending or partial to verified. Its
normative fields stay as they were, its current evidence is kept, and its
`acceptance_evidence` cites acceptance records added by the same transition.
Each accepted resource becomes `accepted` with a reviewed family, a retained
replacement document, reviewed bitmap exceptions, and behavior and visual
evidence that cite acceptance records. The baseline's accepted-resource count
follows the manifest.

## Acceptance records

An acceptance record is a committed JSON document under
`docs/dev/ui/acceptance/`, registered as evidence of kind `acceptance_record`
with its path, SHA-256 and scope. It carries every field the register's
evidence policy requires (`per_acceptance_record_required`) and these in
addition:

| Field | Meaning |
| --- | --- |
| `acceptance_schema` | `1`. |
| `id` | The record's register key. |
| `prepared_by` | Who assembled the evidence. |
| `reviewer_or_review_outcome` | `reviewer`, `outcome` (`accepted`) and ISO `date`; the reviewer cannot be the author. |
| `milestone` | The milestone of the gates the record accepts, otherwise `null`. |
| `executed`, `rendered` | Whether binaries ran and output was rendered; the matching hash, build, host and capture fields are present exactly when true. |
| `requirement_ids`, `resource_ids` | The exact claims. |
| `requirements` | A proof for each claimed requirement. |
| `resources` | A proof for each claimed resource. |

`source_or_asset_hashes` binds tracked files by SHA-256 at `engine_revision`.
Binary, log and image hashes bind the executed and rendered artifacts, which must
exist with those bytes when the transition is audited. Every proof item has a
`result` of `passed` and cites `evidence`: keys of those three hash maps, or
`operation:N` for an entry of `exact_commands_or_operations`.

A requirement proof repeats the requirement's exact current text and proves:

- each `acceptance_evidence_needed` conjunct, in order and word for word;
- each machine-readable constraint key;
- each dependency (below).

The record must also bind every normative source document the requirement cites.

A resource proof names the replacement document (which the record binds), the
manifest's bitmap exceptions and separate `behavior` and `artwork` claims.
Artwork claims must cite a rendered image: source text alone cannot establish
artwork.

The record itself must already exist at `HEAD` with the registered bytes;
an untracked record or an edited working copy cannot grant acceptance. Commit
reviewed records before auditing the acceptance transition. Evidence paths may
not contain control characters, including Git batch-protocol line breaks.

## Dependencies, gates and final acceptance

Dependencies resolve through recorded supersessions to the requirements that
replace them. A proof covers exactly the resolved set:

- A verified dependency is cited by its own acceptance records, which must
  still be current.
- A milestone gate (`GATE-001` to `GATE-006`) may accept its bounded exit scope
  while a broader shared dependency stays partial. The record then proves that
  dependency at the gate's milestone, with a bounded scope statement and
  evidence. Evidence at another milestone does not count, and a pending
  dependency cannot be proved this way.
- A final gate (`FINAL-*`) and the cutover gate `GATE-007` need every
  requirement that a supersession has not replaced verified, apart from the
  final gates themselves, and every migration resource accepted.
- Anything else needs its dependencies verified.

## Staleness and withdrawal

A record goes stale when any file it binds no longer has the recorded bytes, or
when its hashes do not describe its engine revision, or when that revision is
not in the audited history. A transition refuses stale records, including those
of dependencies accepted earlier.

The checkpoint audit applies the same rule to everything accepted before it.
It also rechecks every recorded binary, log and image, including those of
verified dependencies. A replaced executable or missing capture invalidates
the acceptance even when its source files have not changed.
When a change makes an acceptance stale, the increment must either record a new
acceptance or withdraw the old one:

- `--withdraw ID` returns a verified requirement to partial. Its acceptance
  records join its current evidence as history.
- `--withdraw-resource RESOURCE_ID` returns an accepted resource to pending.

Gates follow the same route and are never accepted by a checkpoint.

## Commands

```bash
python tools/ui/validate_product_requirements.py --baseline <HEAD> --acceptance --accept WID-001 --output .tmp/ui/acceptance/<new>.json
```

```bash
python tools/ui/validate_product_requirements.py --baseline <HEAD> --withdraw WID-001 --output .tmp/ui/requirements/<new>.json
```

The baseline is the commit the transition starts from, and the register's
`baseline.engine_revision` names it, as for every other audit.

## Validation

`tools/tests/ui_requirement_acceptance.py` runs the production transition and
checkpoint audits against disposable Git repositories. Its 24 tests cover a
complete acceptance, supersession resolution, a gate's bounded milestone scope,
resource acceptance and a final gate with every requirement and resource. They
also cover the failures the roadmap lists:

- stale evidence and changed sources;
- hashes that do not describe the record's revision, and a revision outside the
  audited history;
- partial conjuncts and constraints;
- missing dependencies, a dependency that skips a supersession, and a
  dependency proved at another milestone or still pending;
- unqualified resources, including missing behavior or artwork, artwork without
  a rendered image, an unreviewed family or bitmap exception, and an unbound
  replacement;
- broad or implicit claims, self-review and incomplete records.
- uncommitted or modified records and control characters in evidence paths;
- logs offered as artwork, nonimage files with image names, and PNG/TGA
  screenshot evidence;
- changed or missing binaries, logs and images after earlier acceptance.

The checkpoint and revision audits still refuse acceptance. A stale acceptance
blocks a checkpoint until it is withdrawn, and a withdrawal must keep its
history. The command line refuses `--accept` without `--acceptance`. The
existing archive and inventory suites pass unchanged, and the current register
passes the extended checkpoint audit.

## Limitations

The transition audits what the records claim against the present files and the
audited history. It does not rerun builds, tests or captures, and it cannot judge
whether a review was competent: it requires every claim to be proved item by
item and reviewed by someone other than its author. Retail assets are not tracked
files, so a record binds them through the manifest's resource identity rather
than by hash. An inventory revision that changes an accepted resource's sources
is not yet reconciled with this route.

The image check recognizes PNG, TGA and JPEG headers; it does not decode the
pixels or judge their visual content. Review still needs the actual rendered
output and the exact scope the record claims. The 28 October review found and
repaired the committed-record, artwork-kind and earlier-artifact checks above;
no product requirement, gate or migration resource was accepted by that review.
