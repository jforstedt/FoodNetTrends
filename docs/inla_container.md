# Isolated INLA container

`containers/foodnet-inla.def` builds a separate, x86_64 image for synthetic
county-model checks. It does not modify `foodnet.def`, `foodnet.sif`, or the
production Nextflow workflow. A successful synthetic check establishes that the
INLA executable runs; it does not validate a FoodNet county model or its inputs.

On a machine configured for Singularity/Apptainer builds, run from this checkout:

```bash
bash scripts/build_inla_container.sh foodnet-inla.sif --fakeroot
```

Omit `--fakeroot` if the build machine provides a different supported privilege
configuration. The script does not request administrator access or submit cluster
jobs. Building needs internet access and compilation resources. Use an appropriate
build allocation on the cluster. An existing output is never overwritten; use a
different filename for another build. The builder prints its log path immediately,
tests the finished image, and publishes the SIF only after the test succeeds.

The definition pins R 4.5.2 through Rocker's published linux/amd64 digest and INLA
26.08.07 through its official source archive and SHA256. The archive hash was
calculated from the official download on 2026-09-12; its repository MD5 is
`3e93d271419222018563f57e391ecc25`. Ubuntu and CRAN dependencies are resolved at
build time, so this is not a fully locked environment. Their installed versions
are recorded inside the image at `/opt/foodnet-inla/installed_packages.csv`, with
R session details at `/opt/foodnet-inla/build_session.txt`. Save the builder's
printed SIF SHA256 alongside results to identify the actual environment used.

Installation errors, missing packages, version mismatches, and a failed synthetic
INLA fit all stop the build. There is no warning-only installation fallback.
The synthetic script is embedded at `/opt/foodnet-inla/inla_smoke.R` and runs with
two INLA threads and one BLAS thread in both build and finished-image checks.

Sources: [Rocker versioned image behavior](https://rocker-project.org/images/versioned/r-ver.html),
[official Rocker tag metadata](https://hub.docker.com/v2/repositories/rocker/r-ver/tags/4.5.2),
[INLA stable package metadata](https://inla.r-inla-download.org/R/stable/src/contrib/PACKAGES),
[pinned INLA archive](https://inla.r-inla-download.org/R/stable/src/contrib/INLA_26.08.07.tar.gz).

## Repair an image built before the executable-permission fix

The official INLA archive installs `inla.mkl.run` and `inla.mkl` with mode 0744:
only the owner can execute them. Root-owned files passed the root build test on
`docker3`, but the SGE job could not execute the launcher as an ordinary user.
The original definition normalized permissions only under `/opt/foodnet-inla`,
not the INLA package directory. The definition now applies `chmod -R a+rX` to INLA
as well. The smoke test checks execute bits explicitly, so root cannot hide this
failure again.

On **docker3 / the container-build host**, reuse the existing image:

```bash
bash scripts/build_inla_container.sh --repair-permissions
```

This derives `foodnet-inla-fixed.sif` from `foodnet-inla.sif`, corrects permissions,
embeds the updated smoke check, and tests it. It does not download or reinstall
packages and does not overwrite the original image. SIF unpacking/compression
still takes time. The corrected image must be accessible on Rosalind.

On **Rosalind**, submit the updated smoke test against the repaired image:

```bash
python3 scripts/launch_inla_smoke.py --container foodnet-inla-fixed.sif
```

The initial SGE smoke run `inla_smoke_20260912_202730_282889` failed before fitting.
The earlier successful image hash was
`5acfc326295d548fc07e704b78879a7f3dd4efd90ec46d941fdc271e1745f763`;
that image's root-host success is not evidence of successful ordinary-user cluster
execution. Keep the new image's checksum with the next result archive.
