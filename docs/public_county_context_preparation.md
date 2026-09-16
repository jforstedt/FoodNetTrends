# Public county context preparation

`scripts/prepare_public_county_context.py` normalizes the already acquired public
USDA agriculture, USGS domestic water-use and ACS crowding extracts documented in
[livestock/water access](historical_livestock_water_access.md) and
[crowding access](historical_crowding_access.md). It reads no case records and fits
no models. Run from the repository root after acquiring those documented inputs:

```bash
python3 scripts/prepare_public_county_context.py --out output/public_county_context_LOCAL
```

The destination must be new. Input directories and county roster are configurable.
The script needs only Python standard-library modules and supports Python 3.6.

Two CSV files retain all roster counties: all historical editions, and fixed
context selected at each requested forecast origin (default December 31 in 2011,
2013 and 2016). Each row records reference year, availability date or conservative
publication-year-end bound, source load timestamp when provided, literal source
value, units and a separate validity status. No interpolation, clipping,
suppression reconstruction, missing-to-zero conversion, or fallback to an older
valid county value occurs. Duplicate keys fail. USDA head inventory, head sold,
and manure-treated acres remain distinct quantities; none is converted to density.

ACS numerator, denominator, all 13 component estimates and their margins of error
remain available. The script rechecks tenure accounting and the derived share.
It does not manufacture a derived-share margin of error. USGS population fractions
require nonnegative finite components and a positive denominator; invalid source
populations remain flagged. Source and output hashes are recorded in the manifest;
USGS and ACS input hashes must match their prior acquisition receipts. Agriculture
selected extracts are hashed but not independently re-extracted from bulk data.

This is a preparation inventory, **not a fit-ready matrix or operational forecast
vintage certification**. Current downloaded historical bytes can include revisions.
An origin-available static county context applied to earlier training outcomes is
an approximation, not a reconstructed monthly exposure history. In particular,
2010 water data are not selected at 2011/2013 origins, and ACS editions are unavailable
until their actual December publication dates. Conservative year-end bounds are
used where the access audit establishes publication year rather than exact date.

The completed local preparation covered 486 counties, 5,832 county-edition rows
and 7,290 county-variable-origin rows. All three crowding editions and 2005 water
have complete numeric coverage. Four 2010 water cells remain invalid. Agriculture
still needs a prespecified suppression/missingness policy and matched evaluation
support: the 2007 export has 477 valid cattle, 253 valid broiler and 461 valid manure
county values. These are public-data availability counts, not clinical results.

Before fitting newer-variable experiments, specify transformations, common support,
ACS uncertainty treatment and interactions (for example water context × rainfall).
A comparison cannot drop counties only in its covariate arm. An explicit fixed-2005
water sensitivity could preserve full coverage; the preparer does not silently
substitute that choice for the latest eligible edition.

Validation: `python3 -m unittest discover -s tests -p test_public_county_context.py`.
Tests cover release-date leakage, suppression/absence/zero distinctions, invalid
water fractions, noncounty water records, duplicate keys, agriculture definitions
and ACS arithmetic/MOE retention. No patient-level data or fit artifacts are
included in this implementation.
