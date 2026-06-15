# Projects

This directory contains definitions for each project currently supported by Mjolnir.

## Existing Projects

- [Caliptra DPE](./caliptra-dpe/): Caliptra's DPE repository.
- [Caliptra MCU SW](./caliptra-mcu-sw/): Caliptra's MCU SW repository.
- [Caliptra SW](./caliptra-sw/): Caliptra's SW repository.
- [OpenTitan](./opentitan/): OpenTitan's main repository.

## Adding a New Project

Creating a new project in Mjolnir is as straightforward as creating a project
definition, one or more job definitions, and the nix infrastructure to support the new project.

```
projects/
└── your_new_project/
    ├── project.nix
    ├── jobs/
    │   └── my_first_job.nix
    └── nix/
        ├── flake.nix
        ├── runner-test.nix
        └── runner.nix
```
