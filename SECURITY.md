# Security policy

## Supported versions

Only the latest release gets security fixes: a fix ships as a new release, and older releases
are not patched. There is no release yet.

| Version                       | Supported |
| ----------------------------- | --------- |
| The latest release (none yet) | Yes       |
| Any earlier release           | No        |

## Reporting a vulnerability

Please report security problems privately, through GitHub's private vulnerability reporting:
open the repository's **Security** tab and press **Report a vulnerability**, or go straight to
<https://github.com/problem-xyz/aion2-map-overlay/security/advisories/new>. Only you and the
maintainer can see the report.

**Do not open a public issue, discussion or pull request for a security problem**, and do not
post it anywhere else before a fix is out. If you are not sure whether something counts, report
it privately anyway.

A useful report says:

- which version you ran (the panel's footer shows it) and your Windows version;
- what an attacker can do, and what they need first, for example getting you to import a file
  or paste a route code;
- the steps to reproduce it, with the route file, share code, object set or map image involved
  if there is one.

## What counts

The app reads files and codes that other people hand you, and it will fetch updates, so these
are the kind of problems this policy is for:

- a route file, share code, object set or map image that makes the app run code, write outside
  its user data folder, or reach the network;
- a way to make the app send data anywhere, or to connect to anything other than GitHub for
  updates;
- anything in the update path that could install something other than a release of this
  project.

A security problem in a dependency, such as Qt, OpenCV or Velopack, belongs with that project
first. Tell us too if the way this app uses it makes the problem reachable.

These are not security problems in the sense of this policy, although a normal issue is welcome
for them: the game's anti-cheat reacting to the overlay, and Windows SmartScreen warning about
an unsigned build.

## What happens next

This is a small project run by one maintainer, so an answer can take a few days. You will hear
whether the report is accepted, and the fix is released before the details are made public.
The published advisory credits you, unless you would rather stay anonymous.
