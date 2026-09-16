# Historical livestock and domestic-water access

Verified 15 September 2026 while the cluster experiment runs. All five requested
historical payloads were downloaded from official public endpoints. Source and
subset receipts are under ignored `output/historical_livestock_water_20260915_LOCAL/`.
No model or pipeline code was changed and nothing was pushed.

## Downloaded agriculture sources

[USDA's official bulk-download index](https://www.nass.usda.gov/datasets/) provides
complete current Quick Stats exports without an API key:

- [2002 agriculture census](https://www.nass.usda.gov/datasets/qs.census2002.txt.gz)
- [2007 agriculture census](https://www.nass.usda.gov/datasets/qs.census2007.txt.gz)

Both gzip files were read through successfully. They are tab-separated, use
uppercase headers, and contain census year, aggregation level, ANSI geography,
commodity/statistic/domain definitions, values and `LOAD_TIME`. County joins use
`STATE_ANSI + COUNTY_ANSI`, not names. The source is a currently served historical
export, not an archived original-release file.

For total-domain, unspecified-domain-category county records:

| Edition | Cattle inventory county records | Suppressed cattle | Broilers sold county records | Suppressed broilers |
|---|---:|---:|---:|---:|
| 2002 | 481 | 4 | 360 | 100 |
| 2007 | 482 | 5 | 365 | 112 |

These counts refer to the 486-county study footprint. The balance is absent
records, not assumed zero. The selected rows and literal suppression tokens are
saved in `ag2002_selected.csv` and `ag2007_selected.csv`. Inventory is head, and
broiler sales are head sold over the reporting period: they are different
quantities, neither a pathogen prevalence nor an automatic density. Any land-area
denominator requires its own matching definition.

Manure is available under `SHORT_DESC=AG LAND - TREATED, MEASURED IN ACRES`,
`DOMAIN_DESC=FERTILIZER`, `DOMAINCAT_DESC=FERTILIZER: (MANURE)`. A search only for
MANURE in the short description or restricting to TOTAL domain would incorrectly
miss it. Acres treated measure land management, not manure mass or microbial load.
The 2002 manure extraction has 472 county records, 21 suppressed; 2007 has 479, 18 suppressed. Both have one selected row per represented county. Literal disclosure suppression remains missing; no reconstruction is attempted.

**Release versus revision.** USDA's history reports final 2002 publications in
June 2004; a contemporary notice scheduled final results for June 3, 2004. The
2007 history identifies February 4, 2009 for the agricultural atlas. Those dates
support historical availability of the editions, but not of every presently
served revised cell. The inspected 2002 selected export rows carry 2012-01-01
load timestamps, so these bytes must not be labelled original 2004 vintage.
[2002 USDA history](https://www.nass.usda.gov/AgCensus/archive/files/2002-History.pdf),
[contemporary 2002 release notice](https://www.nass.usda.gov/nh/pdf/04nepress.pdf),
[2007 USDA history](https://www.nass.usda.gov/AgCensus/archive/files/2007-History-of-the-Census4-7f.pdf)

## Downloaded water-use sources

Official publication-linked files:

- [2000 county water use](https://water.usgs.gov/watuse/data/2000/usco2000.txt)
- [2005 county water use](https://water.usgs.gov/watuse/data/2005/usco2005.txt)
- [2010 county water use](https://water.usgs.gov/watuse/data/2010/usco2010.txt)

They are tab-separated with differing newline conventions and schema additions;
read them using universal newline handling, not physical `head` line counts.
FIPS strings need leading-zero normalization. The candidate domestic self-supply
fraction uses `DO-SSPop / TP-TotPop`, with the source units retained.

| Edition | County identifiers matched | Domestic-population availability | Range check |
|---|---:|---|---|
| 2000 | 485/486 | 103 matched rows lack domestic population: all 95 TN and eight CT counties | Available fractions lie in [0,1] |
| 2005 | 486/486 | All 486 numeric | All fractions lie in [0,1] |
| 2010 | 486/486 | All 486 numeric | Four source values are slightly negative |

The 2000 missing identifier is Broomfield, Colorado (`08014`); do not synthesize
its earlier value without a defensible historical geography crosswalk. Missing
CT/TN domestic values are consistent with the official warning that some states
did not provide county-level domestic estimates in 2000.
[USGS 2000 documentation](https://water.usgs.gov/watuse/data/2000/index.html)

The 2010 negative `DO-SSPop` values occur in MN counties `27033`, `27081`, `27117`
and `27173` (−0.003, −0.004, −0.004, −0.002 respectively). They are source-quality
issues, not valid negative populations. Preserve and flag; do not silently clip
to zero or assert a correction mechanism without source evidence.

USGS's 2005 report was first posted October 27, 2009. The 2010 report is a 2014
publication; 2000 is a 2004 report. Thus 2005 water context can inform a 2011/2013
origin in principle, whereas 2010 water context cannot be treated as available
at those origins. Edition year is not release year. Publication-associated files
are preferable to current revised NWIS values, but current hosting alone still
is not a historical-vintage attestation.
[USGS 2005 release](https://pubs.usgs.gov/circ/1344/index.html),
[USGS 2010 report](https://pubs.usgs.gov/circ/1405/pdf/circ1405.pdf),
[USGS 2000 report](https://pubs.water.usgs.gov/circ1268/pdf/circular1268.pdf),
[USGS download/revision guidance](https://water.usgs.gov/watuse/data/)

## Ready and not-ready decisions

**Ready for a frozen retrospective context pilot:** the 2005 domestic self-supply
measure has full valid footprint coverage. Use it as a fixed county susceptibility
context, potentially interacting with rainfall, not as a monthly contamination
measurement. It does not measure whether a particular patient used untreated
water. Matched comparisons must preserve the existing outcome/exposure domain.

**Ready for a suppression-aware extraction design, not yet a complete model
matrix:** 2002/2007 agriculture provides real pre-origin biological context, but
cattle/broiler missingness and suppression require a common support or explicit
missing-data policy. Do not drop counties only in the covariate arm. Manure has a
verified schema and saved extraction; quantity/denominator choices still need
freezing before models.

**Not ready as a full unrestricted time-varying panel:** 2000 domestic water has
substantial gaps, 2010 has four invalid values, and source release/revision dates
must govern which edition is available at each origin. Do not interpolate through
future editions. An original-vintage operational claim requires archived evidence
beyond today's exports. None of these issues requires changing the running fits.
