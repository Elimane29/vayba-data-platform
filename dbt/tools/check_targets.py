import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from jinja2 import Environment, StrictUndefined
import yaml

ROOT = Path(__file__).resolve().parents[2]
DBT = Path(sys.executable).with_name('dbt')


def main():
    env = dict(os.environ, DBT_SEND_ANONYMOUS_USAGE_STATS='false',
               SNOWFLAKE_ACCOUNT='offline-account', SNOWFLAKE_USER='OFFLINE_USER',
               SNOWFLAKE_PRIVATE_KEY_FILE='/offline/not-opened.p8',
               SNOWFLAKE_ROLE='ROLE_FROM_ENV', SNOWFLAKE_WAREHOUSE='WH_FROM_ENV',
               VAYBA_DEV_SCHEMA='DEV_ROUTING_CHECK')
    jinja = Environment(extensions=['jinja2.ext.do'], undefined=StrictUndefined)
    jinja.globals['env_var'] = lambda name, default=None: env.get(name, default)
    profile = yaml.safe_load(jinja.from_string((ROOT / 'dbt/profiles.yml').read_text()).render())['vayba']['outputs']['prod']
    assert profile['role'] == 'ROLE_FROM_ENV' and profile['warehouse'] == 'WH_FROM_ENV'
    assert profile['schema'] == 'SILVER' and profile['authenticator'] == 'snowflake'
    proof = {'execution_target': 'offline dbt parse and Jinja checks; no Snowflake execution', 'targets': {}}
    with tempfile.TemporaryDirectory() as folder:
        for target, bronze in [('prod', 'BRONZE'), ('dev', 'DEV_HUGO_BRONZE'), ('local', 'DEV_HUGO_BRONZE')]:
            output = Path(folder) / target
            args = [str(DBT), 'parse', '--project-dir', str(ROOT / 'dbt'), '--profiles-dir', str(ROOT / 'dbt'),
                    '--target', target, '--target-path', str(output), '--log-path', str(output / 'logs'), '--no-partial-parse']
            target_env = {key: value for key, value in env.items() if target != 'local' or not key.startswith('SNOWFLAKE_')}
            result = subprocess.run(args, env=target_env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1000:]
            manifest = json.loads((output / 'manifest.json').read_text())
            models = [node for node in manifest['nodes'].values() if node['resource_type'] == 'model']
            assert len(models) == 13
            prefix = '' if target == 'prod' else 'DEV_HUGO_' if target == 'local' else 'DEV_ROUTING_CHECK_'
            for node in models:
                layer = 'GOLD' if '/gold/' in node['original_file_path'] else 'SILVER'
                assert node['schema'] == prefix + layer, (target, node['name'], node['schema'])
            assert {node['schema'] for node in manifest['sources'].values()} == {bronze}
            proof['targets'][target] = {'models': len(models), 'schemas': sorted({node['schema'] for node in models}), 'bronze': bronze}
    schema_source = (ROOT / 'dbt/macros/generate_schema_name.sql').read_text()
    log_source = (ROOT / 'dbt/macros/log_run_results.sql').read_text()
    for name, schema, expected in [('prod', 'SILVER', 'OPS'), ('dev', 'DEV_ROUTING_CHECK', 'DEV_ROUTING_CHECK_OPS')]:
        queries = []
        context = dict(target=SimpleNamespace(name=name, schema=schema, database='VAYBA', type='snowflake'),
                       execute=True, env_var=jinja.globals['env_var'], run_query=queries.append,
                       invocation_id='offline-check', flags=SimpleNamespace(WHICH='build'))
        module = jinja.from_string(schema_source + log_source).make_module(context)
        node = SimpleNamespace(unique_id='model.vayba_dbt.test', resource_type='model')
        module.log_run_results([SimpleNamespace(node=node, status='success', failures=None, execution_time=0.1)])
        if name == 'dev':
            assert queries.pop(0) == 'create schema if not exists VAYBA.' + expected
        assert len(queries) == 2
        assert 'VAYBA.' + expected + '.DBT_RESULTS' in queries[0] and 'VAYBA.' + expected + '.DBT_RESULTS' in queries[1]
        proof['targets'][name]['log_schema'] = expected
    proof['role_and_warehouse_from_environment'] = True
    (ROOT / 'dbt/evidence/target_routing.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
