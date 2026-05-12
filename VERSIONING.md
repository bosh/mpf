# MPF Versioning and Branching

For maintainers.

## SEMVER

MPF users semver, major.minor.patch, though in practice we've only used the minor and patch, releasing nonbreaking upgrades as patches instead of reserving that for bugfixes.

## Branches

`dev` is the development branch. All new-code or bugfix pull requests should be targeted at it.

`0.57.x` and `0.80.x` are the release branches for the released versions 57 and 80. At this point they will only receive bugfix changes,
likely cherry-picked from dev, rather than merging dev changes in

0.80 is the Godot jumping-off point, and it is important for upgrading game developers that 57->80 represents a Legacy MC to GMC transition smoothly,
with minimal other configuration changes required (mostly event names for the built-in mode features).

`0.81.x` is the development branch for the next release of MPF, including breaking changes to FAST light config requirements as well as general randomizer behaviors.

0.81 is an intentional break from 80 and thus 57, so some features will not be backported to the legacy MC era MPF.

`0.58.x` is the development branch for the legacy era MPF, where some features (like the FAST lights) will be ported, but other features (like randomizer)
are too different between 57 and 80+ to continue supporting in a backwards-compatible way.

## Releasing

### Bugfixing 57/80 (Latest full releases, in maintenaince support now, not receiving new features)

To release a bugfix version of 57 or 80, first locally check out the development branch (e.g. `0.57.x`) from missionpinball.

Then cherry-pick the relevant commit onto your local copy, then commit a separate version bump commit that increments the current dev version,
or if moving to a new patch, add .dev1 on the patch number (e.g. `0.57.5` -> `0.57.6.dev1`).i
Push that to your fork, and then make a PR from your fork onto the missionpinball .x branch target.

After the change is accepted and merged, a maintainer will need to tag the bump commit (should be the head of the .x branch) with a matching
version string, such as `v0.57.6.dev1` and push the tag to Github.

### Releasing dev work to 58 (Legacy Development) / 81 (Modern)

To release net-new work to the active development versions, first get your work merged onto `dev` (for either). If `dev` is too different from
the legacy version, target the legacy .x branch instead (this should only be true for some lights code and some randomizer code).

In general both 58 and 81 should be released together, to keep differences limited to only the intentionally breaking changes.

To release, check out the latest .x branch from missionpinball, then merge (with a merge commit) `dev` into it.
Then make a version bump commit (revving patch or minor as appropriate).
Push the merge+bump to your fork and make a PR from your .x branch to the origin .x branch.
After that PR is merged, a maintainer must make a version bump tag and push it to Github.

#### Note for incompatible 58/81 changes

If a dev change only makes sense for 81 to take, still always make the PR on `dev`.
After the change is merged into `dev`, merge the incompatible `dev` code into `0.58.x`
with a merge strategy like `-s ours` so that the modern changes are not brought into legacy.

## What version string on `dev`?

The latest working version of Modern MPF (so 0.81.#.dev#) should be used, to reduce effort release bumping 81
and to ensure dev is considered compatible for the dev version of GMC, as both tools require minimum versions of the other.

