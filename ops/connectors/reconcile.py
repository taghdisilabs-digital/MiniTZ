#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path('/var/lib/minitz')
IMPLEMENTATION = Path('/usr/lib/minitz/connectors/minitz-connectors.py')
PROVIDER_CHECK = Path('/usr/local/lib/minitz-workstation/minitz-provider-check.sh')
BROWSER_CHECK = Path('/usr/local/bin/minitz-browser-cloud')
VERIFIER = Path('/usr/lib/minitz/connectors/minitz-private-secret-verifier.py')
PROVIDER_ENV = ROOT / 'credentials/providers.env'
CREDENTIAL_REGISTRY = ROOT / 'credentials/registry.json'
PROVIDER_DECLARATIONS = ROOT / 'resources/provider-declarations.json'
RESOURCE_REGISTRY = ROOT / 'resources/connectors.json'
ACCOUNT_EVIDENCE = ROOT / 'evidence/provider-accounts-2026-09-12.json'
VALIDATION_EVIDENCE = ROOT / 'evidence/connectors-validation-2026-09-12.json'
SUMMARY = ROOT / 'system/connectors-summary.json'
OWNER_POLICY = ROOT / 'system/resource-owner-policy.json'

def load_module() -> Any:
    spec = importlib.util.spec_from_file_location('minitz_connectors_runtime', IMPLEMENTATION)
    if spec is None or spec.loader is None:
        raise RuntimeError('MiniTZ connector implementation is unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args: list[str], *, env: dict[str, str] | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, env=env, timeout=timeout, check=False)


def provider_probe() -> tuple[str, dict[str, str]]:
    env = os.environ.copy()
    env['MINITZ_AI_RUNTIME_ENV'] = str(PROVIDER_ENV)
    proc = run([str(PROVIDER_CHECK)], env=env)
    if proc.returncode != 0:
        raise RuntimeError('provider validation command failed')
    return proc.stdout, env


def github_validation() -> dict[str, Any]:
    proc = run(['gh', 'api', 'user', '--jq', '.login'], timeout=15)
    if proc.returncode == 0 and proc.stdout.strip():
        return {'availability':'Ready','availability_reason':'ready','credential_ref':'credential.external.github_cli','support_tier':'Managed','capabilities':['source.repository','source.publish'],'implementation_source':'github_cli'}
    return {'availability':'Needs Setup','availability_reason':'authentication_required','support_tier':'Managed','capabilities':['source.repository','source.publish'],'implementation_source':'github_cli'}

def openai_validation() -> dict[str, Any]:
    proc = run(['codex', 'login', 'status'], timeout=15)
    status_text = (proc.stdout or '') + '\n' + (proc.stderr or '')
    logged_in = proc.returncode == 0 and 'Logged in using ChatGPT' in status_text
    if logged_in:
        return {'availability':'Ready','availability_reason':'ready','credential_ref':'credential.external.openai_chatgpt_codex','support_tier':'Managed','capabilities':['assistant.interactive','llm.code','llm.reasoning'],'implementation_source':'codex_chatgpt_login'}
    return {'availability':'Needs Setup','availability_reason':'authentication_required','support_tier':'Managed','capabilities':['assistant.interactive','llm.code','llm.reasoning'],'implementation_source':'codex_chatgpt_login'}


def browser_evidence() -> dict[str, Any]:
    proc = run([str(BROWSER_CHECK), 'status'], timeout=25)
    if proc.returncode != 0:
        return {'account_confirmed':True,'availability':'Unavailable','availability_reason':'health_check_failed','evidence':['runtime:windows-browser-cloud']}
    try:
        payload = json.loads(proc.stdout)
        result = payload.get('result', {})
    except json.JSONDecodeError:
        result = {}
    targets = result.get('targets', []) if isinstance(result, dict) else []
    full_target = bool(targets) and all(bool(item.get('found')) for item in targets if isinstance(item, dict))
    if result.get('status') == 'READY' and full_target:
        state, reason = 'Ready', 'ready'
    elif result.get('status') == 'READY':
        state, reason = 'Degraded', 'health_check_failed'
    else:
        state, reason = 'Unavailable', 'health_check_failed'
    return {'account_confirmed':True,'availability':state,'availability_reason':reason,'evidence':['runtime:windows-browser-cloud']}


def external_registry(registry: dict[str, Any]) -> dict[str, Any]:
    external_ids = {pid for pid, provider in registry['providers'].items() if provider.get('required_env') or pid in {'modal','saturn','windows-browser-cloud'}}
    registry = json.loads(json.dumps(registry))
    registry['providers'] = {pid: provider for pid, provider in registry['providers'].items() if pid in external_ids}
    for capability, route in list(registry.get('routes', {}).items()):
        registry['routes'][capability] = [pid for pid in route if pid in external_ids]
    return registry

def apply_owner_policy(inventory: dict[str, Any], policy: dict[str, Any]) -> None:
    if isinstance(policy.get('owner_exclusions'), list):
        inventory['owner_exclusions'] = [str(item) for item in policy['owner_exclusions']]
    resources = inventory.get('resources', {})
    for resource_id, override in policy.get('resource_overrides', {}).items():
        resource = resources.get(resource_id)
        if resource is None or not isinstance(override, dict):
            continue
        resource.update(json.loads(json.dumps(override)))


def qualify_inventory(inventory: dict[str, Any]) -> None:
    supabase = inventory['resources'].get('resource.provider.supabase')
    if supabase:
        supabase['credential_refs'] = sorted(set(supabase.get('credential_refs', []) + ['credential.provider.supabase.minitzos_oauth_client_secret']))
        supabase_config = load_module().parse_env_file(ROOT / 'credentials/supabase/minitzos-oauth.env')
        supabase['project_ref'] = supabase_config.get('SUPABASE_PROJECT_REF')
        supabase['oauth_client_id'] = supabase_config.get('SUPABASE_OAUTH_CLIENT_ID')
    for resource_id, resource in inventory['resources'].items():
        if resource.get('availability') == 'Ready' and resource_id.startswith('resource.provider.'):
            resource['connection_validation'] = 'credential_and_service_access'
            resource['capability_readiness'] = 'requires_capability_specific_functional_test'
        elif resource_id == 'resource.account.github' and resource.get('availability') == 'Ready':
            resource['connection_validation'] = 'authenticated_account_api_access'
            resource['capability_readiness'] = 'source_account_access_validated'


def run_secret_verifier(secret_source: Path, receipt: Path) -> str:
    targets = [RESOURCE_REGISTRY, ACCOUNT_EVIDENCE, VALIDATION_EVIDENCE, SUMMARY]
    args = [str(VERIFIER), '--secret-source', str(secret_source)]
    for target in targets:
        args += ['--target', str(target)]
    args += ['--receipt', str(receipt)]
    proc = run(['python3', *args], timeout=30)
    if proc.returncode != 0:
        raise RuntimeError('secret leak validation did not pass')
    payload = json.loads(proc.stdout)
    return str(payload.get('result'))

def refresh() -> dict[str, Any]:
    module = load_module()
    registry = external_registry(json.loads(PROVIDER_DECLARATIONS.read_text(encoding='utf-8')))
    selected, invalid = module.select_provider_values(registry, module.parse_env_file(PROVIDER_ENV))
    output, _ = provider_probe()
    states = module.parse_provider_check(output, registry)
    account_payload = json.loads(ACCOUNT_EVIDENCE.read_text(encoding='utf-8'))
    accounts = dict(account_payload['accounts'])
    accounts['Windows Browser Cloud'] = browser_evidence()
    external = {'GitHub': github_validation(), 'OpenAI': openai_validation()}
    inventory = module.build_resource_inventory(registry, selected, invalid, states, accounts, external)
    inventory['observed_at'] = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    inventory['authority'] = 'MINITZ_RUNTIME_STATE'
    inventory['owner_exclusions'] = ['Google','Gemini']
    qualify_inventory(inventory)
    if OWNER_POLICY.exists():
        policy = json.loads(OWNER_POLICY.read_text(encoding='utf-8'))
        apply_owner_policy(inventory, policy)
        inventory['owner_policy_ref'] = str(OWNER_POLICY)
    module.write_json_protected(RESOURCE_REGISTRY, inventory)
    validation = {'schema':'minitz.connector_validation/v1','observed_at':inventory['observed_at'],'probe_output':output.splitlines(),'secret_values_included':False}
    module.write_json_protected(VALIDATION_EVIDENCE, validation)
    counts = Counter(resource['availability'] for resource in inventory['resources'].values())
    summary = {'schema':'minitz.connector_summary/v1','observed_at':inventory['observed_at'],'resource_count':len(inventory['resources']),'availability_counts':dict(counts),'google_gemini_excluded':True,'canonical_credential_source':str(PROVIDER_ENV),'canonical_resource_registry':str(RESOURCE_REGISTRY)}
    module.write_json_protected(SUMMARY, summary)
    summary['provider_secret_leak_check'] = run_secret_verifier(PROVIDER_ENV, ROOT / 'evidence/provider-secret-leak-receipt.json')
    summary['supabase_oauth_secret_leak_check'] = run_secret_verifier(ROOT / 'credentials/supabase/minitzos-oauth.env', ROOT / 'evidence/supabase-oauth-secret-leak-receipt.json')
    return summary

def print_resources() -> None:
    payload = json.loads(RESOURCE_REGISTRY.read_text(encoding='utf-8'))
    for resource in sorted(payload['resources'].values(), key=lambda item: str(item['service_identity']).lower()):
        print(f"{resource['service_identity']}\t{resource['availability']}\t{resource['availability_reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(prog='minitz-connectors')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('refresh'); sub.add_parser('status'); sub.add_parser('resources'); sub.add_parser('providers'); sub.add_parser('accounts')
    args = parser.parse_args()
    if args.command == 'refresh':
        print(json.dumps(refresh(), sort_keys=True)); return 0
    if args.command == 'status':
        print(SUMMARY.read_text(encoding='utf-8'), end=''); return 0
    if args.command == 'resources':
        print_resources(); return 0
    if args.command == 'providers':
        output, _ = provider_probe(); print(output, end=''); return 0
    payload = json.loads(ACCOUNT_EVIDENCE.read_text(encoding='utf-8'))
    for name, item in sorted(payload['accounts'].items()):
        print(f"{name}\t{'CONFIRMED' if item.get('account_confirmed') else 'PENDING'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
