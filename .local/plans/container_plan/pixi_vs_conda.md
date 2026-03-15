# Pixi vs Conda for FoodNetTrends Container Builds

## 1. What Is Pixi?

Pixi is a cross-platform package manager written in Rust by prefix.dev. It is built
on top of the conda ecosystem -- it uses the same package repositories (conda-forge,
bioconda, etc.) and the same package format. The key differences from conda/mamba:

- **Workspace-oriented, not environment-oriented.** Pixi creates a `pixi.toml`
  manifest and a `.pixi/` directory inside your project folder. Environments are
  local to the project, not stored in `~/miniconda3/envs/`.
- **Built-in lock file.** `pixi.lock` is generated automatically on every install.
  No separate tool (like conda-lock) is needed.
- **Rust-based solver.** Roughly 10x faster than conda, 3-4x faster than mamba/
  micromamba for environment resolution and installation.
- **First-class PyPI support.** Can resolve conda and pip packages together in a
  single lock file (not relevant for this pipeline, which is pure R/conda).
- **Task runner.** You can define `[tasks]` in pixi.toml (like a Makefile) -- a
  convenience, not a game-changer.

Pixi is **not** a fork of conda. It is a new frontend that talks to the same
repositories and installs the same packages.

## 2. Does Pixi Support the R Packages This Pipeline Needs?

**Yes.** Pixi installs packages from conda-forge and bioconda -- the exact same
channels the current `foodnet.yml` uses. Every package in `foodnet.yml` is a
conda-forge package and would be available via pixi:

| Package        | conda-forge name | Available via pixi? |
|----------------|-----------------|---------------------|
| r-base=4.3.2   | r-base          | Yes                 |
| r-argparse     | r-argparse      | Yes                 |
| r-tidyverse    | r-tidyverse     | Yes                 |
| r-dplyr        | r-dplyr         | Yes                 |
| r-haven        | r-haven         | Yes                 |
| r-gtools       | r-gtools        | Yes                 |
| r-brms         | r-brms          | Yes                 |
| r-reshape2     | r-reshape2      | Yes                 |
| r-ggplot2      | r-ggplot2       | Yes                 |
| r-tidybayes    | r-tidybayes     | Yes                 |
| r-HDInterval   | r-hdinterval    | Yes                 |
| r-cmdstanr     | r-cmdstanr      | Yes                 |
| r-rstan        | r-rstan         | Yes                 |
| r-gridExtra    | r-gridextra     | Yes                 |

Pixi uses the same underlying packages. If conda can install it, pixi can install it.

## 3. Is Pixi Compatible with Singularity/Apptainer Builds?

**Yes, but the approach changes slightly.**

### Current approach (conda):
```
Bootstrap: docker
From: continuumio/miniconda3
%post
    conda env create -f foodnet.yml
```

### Pixi approach (two options):

**Option A: Install pixi in the .def file directly**
```
Bootstrap: docker
From: ubuntu:22.04
%post
    curl -fsSL https://pixi.sh/install.sh | bash
    export PATH="$HOME/.pixi/bin:$PATH"
    cd /opt/project
    pixi install --locked
```

**Option B: Multi-stage Docker build, then convert to .sif**
Build a Docker image with pixi, then convert:
```
apptainer build container.sif docker://myregistry/foodnet:latest
```

Option A is simpler and closer to the current workflow. Option B is better if you
want CI/CD to build Docker images that get converted to .sif for HPC.

There are no fundamental incompatibilities. The pixi environment is just a directory
of conda packages -- Singularity can use it the same way it uses a conda env.

## 4. Concrete Advantages Over Conda for This Use Case

### Advantages of pixi:
1. **Built-in lock file.** The current `foodnet.yml` pins versions but has no lock
   file. This means transitive dependencies are not pinned. Two builds at different
   times could produce different environments. Pixi's `pixi.lock` pins every
   transitive dependency with hashes. This is the single biggest practical advantage.

2. **Faster builds.** Container builds would be faster because pixi resolves and
   installs 3-10x faster than conda. For an R environment with Stan (which has many
   compiled dependencies), this matters.

3. **No Miniconda base image needed.** The pixi binary is ~30 MB. You can start from
   a minimal Ubuntu image instead of `continuumio/miniconda3` (which is ~400 MB).
   This produces smaller containers.

4. **Project-local environments.** The environment lives in `.pixi/` next to the
   code. No `conda activate` or PATH manipulation needed if using `pixi run`.

5. **Avoids Anaconda licensing.** The current `foodnet.yml` includes the `defaults`
   channel, which is Anaconda's proprietary channel and may require a license for
   organizational use. Pixi defaults to conda-forge, which avoids this issue.

6. **No environment name typos.** The current `foodnet.yml` has the environment name
   `FootNetTreands_R` (misspelled). With pixi, the environment is anonymous and
   project-local -- no name to get wrong.

### Advantages that don't matter for this use case:
- PyPI integration (no Python packages in this pipeline)
- Multi-environment support (only one environment needed)
- Task runner (SGE/Nextflow handles task execution)

## 5. Lock File Comparison

| Feature                  | conda (current)     | conda-lock           | pixi                  |
|--------------------------|--------------------|-----------------------|-----------------------|
| Lock file                | None by default    | conda-lock.yml        | pixi.lock (automatic) |
| Transitive dep pinning   | No                 | Yes                   | Yes                   |
| Hash verification        | No                 | Yes                   | Yes                   |
| Speed of lock generation | N/A                | Slow (minutes)        | Fast (seconds)        |
| Extra tooling needed     | No                 | Yes (conda-lock)      | No                    |
| Cross-platform locks     | N/A                | Yes                   | Yes                   |
| Conda + PyPI combined    | No                 | Limited               | Yes                   |

The current setup (`foodnet.yml` with pinned versions) provides partial
reproducibility. The version pins ensure the direct dependencies match, but
transitive dependencies (e.g., which exact build of libstanmath gets pulled) can
drift. Pixi solves this completely with its built-in lock file.

A converter exists (`pixi-to-conda-lock`) if you ever need to go back to
conda-lock.yml format.

## 6. Maturity Assessment

| Criterion                        | Status                                        |
|----------------------------------|-----------------------------------------------|
| First release                    | 2023                                          |
| Current version (as of early 2026) | v0.40+ (active development)                 |
| Backed by                        | prefix.dev (company, funded)                  |
| Used in production               | Yes (QuantCo, various HPC centers)            |
| HPC documentation                | Oregon State, DESY Maxwell cluster, others    |
| Conda ecosystem endorsement      | conda-lock project suggests pixi for new work |
| Breaking changes risk            | Low -- manifest format is stable               |
| Bus factor                       | Moderate -- backed by a company, not one person|

**Assessment:** Pixi is mature enough for production HPC use. It is past the
early-adopter phase. Oregon State and DESY (German particle physics lab) have
official HPC documentation for pixi. The conda-lock maintainers themselves have
suggested pixi as the future of environment locking in the conda ecosystem.

That said, conda is extremely battle-tested. If the current setup is not causing
problems, there is no urgent need to switch.

## 7. Migration Path

Migration from `foodnet.yml` to pixi is straightforward:

```bash
# One command to import the existing conda yml:
pixi init --import foodnet.yml

# This creates:
#   pixi.toml     (manifest with all deps and channels)
#   pixi.lock     (complete lock file)
#   .pixi/        (local environment directory)
```

The resulting `pixi.toml` would look approximately like:

```toml
[project]
name = "FoodNetTrends"
channels = ["conda-forge", "bioconda"]
platforms = ["linux-64"]

[dependencies]
r-base = "4.3.2"
r-argparse = "2.2.5"
r-tidyverse = "2.0.0"
r-dplyr = "1.1.4"
r-haven = "2.5.4"
r-gtools = "3.9.5"
r-brms = "2.22.0"
r-reshape2 = "1.4.4"
r-ggplot2 = "3.5.1"
r-tidybayes = "3.0.7"
r-hdinterval = "0.2.4"
r-cmdstanr = "0.8.1"
r-rstan = "2.32.6"
r-gridextra = "2.3"
```

The `foodnet.def` would need to be updated to use pixi instead of conda.
This is a small change (see Section 3 above).

**Note:** The current `foodnet.yml` lists channels `defaults`, `r`, and `stan` in
addition to `conda-forge` and `bioconda`. During migration, verify that all packages
resolve from just `conda-forge` and `bioconda`. If any packages require the `stan`
or `r` channels specifically, those channels would need to be added to the pixi.toml.
The `defaults` channel is Anaconda's proprietary channel and may require a license
for organizational use -- pixi defaults to conda-forge, which avoids this issue.

## 8. Gotchas and Potential Dealbreakers

### Not dealbreakers, but worth knowing:

1. **No `pixi activate` in Singularity runscript.** Inside a container, you cannot
   run `pixi shell` interactively. You would use `pixi run <command>` or set PATH
   manually to point to the `.pixi/envs/default/bin/`. Alternatively, use
   `pixi shell-hook` to generate the activation script. This is solvable but
   requires adjusting the .def file.

2. **pixi must be installed in the container.** The current approach uses a
   miniconda3 base image. With pixi, you either install pixi via curl in `%post` or
   use the `ghcr.io/prefix-dev/pixi` base image. Both work fine.

3. **Team familiarity.** If the team knows conda well and is not experiencing
   reproducibility issues, the learning curve (small as it is) may not be worth it.

4. **Channel compatibility.** The `stan` and `r` channels in the current yml are
   non-standard. Most R/Stan packages are on conda-forge, but this needs to be
   verified during migration. If a package is only on the `stan` channel and not on
   conda-forge, pixi can still use that channel -- but you need to check.

5. **Singularity cache on HPC.** Pixi stores packages in a global cache
   (`~/.cache/rattler/`). Inside a container this is fine (ephemeral). But if anyone
   tries to use pixi directly on the HPC login nodes, they need to be aware of home
   directory quota limits and may need to redirect the cache.

### Not an issue:

- **Package availability:** All packages in `foodnet.yml` are standard conda-forge
  packages. Pixi will find them.
- **Platform support:** `linux-64` is fully supported, which is what Rosalind
  (SGE cluster) runs.
- **Stability:** Pixi is stable enough for production use.

## Bottom Line Recommendation

**Pixi is a genuine improvement over raw conda for this use case, primarily because
of the built-in lock file.** The current `foodnet.yml` pins direct dependency
versions but does not lock transitive dependencies. This means builds are not fully
reproducible over time. Pixi fixes this without requiring a separate tool like
conda-lock.

**However, conda is not broken here.** If the team is building containers
infrequently and the current setup works, switching to pixi is a nice-to-have, not
a must-have. The strongest argument for switching is if you want guaranteed
reproducibility (e.g., rebuilding the container in 6 months and getting the exact
same environment).

**If you do switch**, the migration is low-risk: one import command, a small .def
file change, and verification that all packages resolve. The fallback path (going
back to conda) is trivial since pixi uses the same packages.

---

## Sources

- [7 Reasons to Switch from Conda to Pixi](https://prefix.dev/blog/pixi_a_fast_conda_alternative)
- [Pixi/uv: Bioinformatics Powerhouse](https://josephguhlin.com/pixi-uv-bioinformatics-powerhouse/)
- [Simplify Your Bioinformatics Workflow with Pixi](https://edmundmiller.dev/posts/pixi-bioinformatics/)
- [Shipping conda environments to production using pixi (QuantCo)](https://tech.quantco.com/blog/pixi-production)
- [Pixi Container Deployment docs](https://pixi.prefix.dev/latest/deployment/container/)
- [Deploying Pixi environments with Linux containers (Carpentries)](https://carpentries-incubator.github.io/reproducible-ml-workflows/pixi-deployment.html)
- [Switching from Conda to Pixi (official docs)](https://pixi.prefix.dev/latest/switching_from/conda/)
- [Pixi - Oregon State University HPC Documentation](https://docs.hpc.oregonstate.edu/cqls/software/conda/pixi/)
- [conda-lock: Should we endorse Pixi?](https://github.com/conda/conda-lock/issues/615)
- [pixi-to-conda-lock converter](https://github.com/basnijholt/pixi-to-conda-lock)
- [Pixi production discussion on GitHub](https://github.com/prefix-dev/pixi/discussions/1444)
- [Conda + Pixi Quick Start Guide (Anaconda)](https://www.anaconda.com/blog/conda-pixi-quick-start-guide-python-environment-management)
