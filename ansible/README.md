# MQ Object Dump Extraction Automation

This Ansible playbook automates the process of generating the `qmgr_dump.csv` manifest file required by the MQ MCP Server. It works natively through Ansible, requiring only standard MQ binaries (`dspmq` and `dmpmqcfg`) on the target servers, without needing any custom Python scripts deployed to the targets.

## Overview

The `extract_qmgrs_manifest.yml` playbook performs the following workflow:
1. Connects to all hosts in the `[mq_servers]` inventory.
2. Identifies all running Queue Managers automatically using `dspmq`.
3. Runs `dmpmqcfg -a -o 1line` for each Queue Manager to dump object definitions in a standardized single-line format.
4. Uses Jinja2 templating within Ansible to parse these raw dumps in-memory.
5. Formats the data into `extractedat|hostname|qmname|objecttype|objectdef`.
6. Aggregates the formatted CSV blocks from all servers.
7. Writes the comprehensive dump straight into `../resources/qmgr_dump.csv`.

## Prerequisites

- Ansible (v2.9+ recommended) installed on the control machine.
- Network access to the target MQ servers.
- An account on the target servers with enough privileges to run `dspmq` and `dmpmqcfg` (typically the `mqm` user).

## Configuration

1. Copy the example inventory:
   ```bash
   cp inventory.ini.example inventory.ini
   ```
2. Edit `inventory.ini` to add your MQ servers and update your connection parameters (SSH keys or WinRM configurations).

## Running the Manifest Extraction

Run the playbook directly using the `ansible-playbook` command from this directory:

```bash
ansible-playbook -i inventory.ini extract_qmgrs_manifest.yml
```

Once execution is complete, verify that the manifest was generated properly.
```bash
head -n 5 ../resources/qmgr_dump.csv
```

## Scheduling (Optional)

In a production setting, since queue manager topologies change over time, it is highly recommended to schedule this playbook to run periodically (e.g. nightly via cron, Jenkins, Ansible Tower, or AWX). This ensures that the MQ MCP Agent always has an up-to-date offline topology of your systems for the `find_mq_object` tool to ingest.
